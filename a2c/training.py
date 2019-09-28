"""
File: training
Date: 2019-07-25 
Author: Jon Deaton (jonpauldeaton@gmail.com)

Inspired by:
    - http://inoryy.com/post/tensorflow2-deep-reinforcement-learning/
    - https://github.com/MG2033/A2C/
    
"""

from a2c.hyperparameters import HyperParameters
from a2c.rollout import Rollout
from a2c.async_coordinator import AsyncCoordinator
from a2c.eager_models import ConvLSTMAC, LSTMAC, get_encoder_type
from a2c.losses import *

import os
from tqdm import tqdm
import numpy as np
import tensorflow as tf
import tensorflow.keras.optimizers as ko

import logging
logger = logging.getLogger("root")
logger.propagate = False


def get_rollout(model, env, agents_per_env, episode_length, to_action) -> Rollout:
    """ performs a roll-out """
    rollout = Rollout()

    observations = env.reset()

    dones = [False] * agents_per_env

    model.reset_states()
    for _ in range(episode_length):
        if all(dones): break

        obs_tensor = tf.expand_dims(tf.convert_to_tensor(observations), axis=1)
        action_logits, est_values = model(obs_tensor)

        # sample the action
        actions = tf.squeeze(tf.random.categorical(tf.squeeze(action_logits, axis=1), 1), axis=-1).numpy()
        values = list(tf.squeeze(est_values, axis=[1, 2]).numpy())

        next_obs, rewards, next_dones, _ = env.step(list(map(to_action, actions)))

        rollout.record(observations, actions, rewards, values, dones)
        dones = next_dones
        observations = next_obs

    return rollout


class Trainer:

    def __init__(self, get_env, hyperams: HyperParameters, to_action, test_env=None, training_dir=None):
        self.get_env = get_env
        self.hyperams = hyperams
        self.to_action = to_action
        self.test_env = test_env

        self.num_envs = hyperams.num_envs

        self._set_seed(hyperams.seed)

        # build the actor-critic network
        encoder_type = get_encoder_type(hyperams.encoder_class)

        if hyperams.architecture == 'LSTM':
                self.model = LSTMAC(hyperams.action_shape, encoder_type)
        elif hyperams.architecture == 'ConvLSTM':
            self.model = ConvLSTMAC(hyperams.action_shape)
        else:
            raise ValueError(hyperams.architecture)

        self.optimizer = ko.Adam(lr=hyperams.learning_rate, clipnorm=1.0)

        # env = get_env()
        # input_shape = (None, ) + env.observation_space.shape

        # inputs = tf.keras.Input(input_shape)
        # self.model._set_inputs(inputs)

        # self.model.build((None, ) + input_shape)

        # del env

        self.training_dir = training_dir
        self.tensorboard = None
        if training_dir is not None:
            self.summary_writer = tf.summary.create_file_writer(training_dir)
            self.tensorboard = tf.keras.callbacks.TensorBoard(log_dir=training_dir,
                                                              histogram_freq=1)

    def train(self, asynchronous=False):
        """ trains a model """
        if asynchronous:
            self._train_async()
        else:
            self._train_sync()

    def _train_sync(self):
        """ trains a model sequentially with a single environment """
        env = self.get_env()

        for ep in range(self.hyperams.num_episodes):
            rollout = get_rollout(self.model, env,
                                  self.hyperams.agents_per_env,
                                  self.hyperams.episode_length,
                                  self.to_action)

            self._update_with_rollout(rollout)

    def _train_async(self):
        """ trains a model asynchronously """

        if self.training_dir is None:
            raise ValueError

        def _get_rolllout(model, env):
            return get_rollout(model, env, self.hyperams.agents_per_env,
                         self.hyperams.episode_length, self.to_action)

        model_directory = os.path.join(self.training_dir, "model")

        logger.info("Saving model")
        self.model.save(model_directory, include_optimizer=False)
        logger.info("Model saved.")

        coordinator = AsyncCoordinator(self.hyperams.num_envs,
                                       model_directory,
                                       self.get_env,
                                       _get_rolllout)

        with coordinator:
            for ep in range(self.hyperams.num_episodes):
                rollout = coordinator.await_rollout()
                self._log_rollout(rollout, ep)
                self._update_with_rollout(rollout)
                self.model.save(model_directory)

    def _train_async_shared(self):
        """ trains asynchronously with a single shared model
        todo: this is interesting but ultimately garbage... try make better someday?
        """
        from a2c.shared_async_coordinator import AsyncCoordinatorShared
        import threading
        lock = threading.Lock()

        def get_actions(observations, carry):
            obs_in = tf.convert_to_tensor(observations)
            with lock:
                actions_t, values_t, carry = self.model.cell.action_value(obs_in, carry)

            # convert Tensors to list of action-indices and values
            actions = actions_t.numpy()
            values = list(values_t.numpy())

            return actions, values, carry

        def initialize():
            with lock:
                return self.model.cell.get_initial_state(batch_size=self.hyperams.agents_per_env,
                                                   dtype=tf.float32)

        coordinator = AsyncCoordinatorShared(self.hyperams.num_envs, self.get_env,
                                       self.hyperams.episode_length,
                                       initialize, get_actions, self.to_action)

        with coordinator:
            for ep in range(self.hyperams.num_episodes):
                rollout = coordinator.await_rollout()
                self._log_rollout(rollout, ep)
                self._update_with_rollout(rollout)

    def _update_with_rollout(self, rollout):
        """ updates the network using a roll-out """
        observations, actions, rewards, values, dones = rollout.as_batch()

        returns = make_returns_batch(rewards, self.hyperams.gamma)

        obs_batch = np.array(observations)
        act_batch = np.array(actions)
        ret_batch = np.array(returns)
        val_batch = np.array(values)
        adv_batch = ret_batch - val_batch
        mask = tf.convert_to_tensor(np.logical_not(np.array(dones)), dtype=tf.bool)

        loss_vars = obs_batch, mask, act_batch, adv_batch, ret_batch
        (a_loss_val, c_loss_val), grads = a2c_loss(self.model, *loss_vars)
        logger.info(f"Actor loss: {a_loss_val:.3f}, Critic loss: {c_loss_val:.3f}")

        logger.info(f"Applying gradients...")
        self.optimizer.apply_gradients(zip(grads, self.model.trainable_variables))

    def _log_rollout(self, rollout, episode):
        """ logs the performance of the roll-out """
        _, _, rewards, _, _ = rollout.as_batch()
        Gs = np.array([rs.sum() for rs in rewards])  # episode returns
        print(f"Episode {episode} returns: {Gs.min():.0f} min. {Gs.mean():.1f} ± {Gs.std():.0f} avg. {Gs.max():.0f} max.")

    def test(self):
        return
        logger.info(f"Testing performance...")
        o = self.test_env.reset()
        rewards = []
        done = False
        lstm_state = np.zeros(32)
        for t in tqdm(range(self.hyperams.episode_length)):
            if not done:
                a, lstm_state = self.model.action(np.expand_dims(o, axis=0), lstm_state)
                o, r, done, _ = self.test_env.step(self.to_action(a))
                rewards.append(r)

        episode_len = len(rewards)
        rewards = np.array(rewards)
        G = rewards.sum()
        mass = rewards.cumsum() + 10

        pellet_density = self.hyperams.num_pellets / pow(self.hyperams.arena_size, 2)
        efficiency = G / (episode_len * pellet_density)

        print(f"Return: {G:.0f}, max mass: {mass.max():.0f}, avg. mass: {mass.mean():.1f}, efficiency: {efficiency:.1f}")

    def _set_seed(self, seed):
        # todo: this isn't everywhere that it needs to be set
        np.random.seed(seed)
        tf.random.set_seed(seed)
