"""
File: Actor
Date: 2019-07-28 
Author: Jon Deaton (jdeaton@stanford.edu)
"""

import tensorflow as tf
import tensorflow.keras.layers as kl

import numpy as np


class Distribution(tf.keras.Model):
    def call(self, logits):
        return tf.squeeze(tf.random.categorical(logits, 1), axis=-1)


class ActorCritic(tf.keras.Model):
    def __init__(self, action_shape):
        super(ActorCritic, self).__init__()
        self.conv = kl.Conv2D(32, 3, activation=tf.nn.relu)
        self.flatten = kl.Flatten()

        self.value_layer = kl.Dense(1, activation=None)

        self.action_shape = action_shape
        action_size = np.prod(action_shape)
        self.action_layer = kl.Dense(action_size, activation=tf.nn.softmax)

        self.action_distribution = Distribution()

    def call(self, x: tf.Tensor):
        x = tf.dtypes.cast(x, tf.float32)
        x = self.conv(x)
        x = self.flatten(x)

        action_param = self.action_layer(x)
        values = self.value_layer(x)
        return action_param, values

    def action_value(self, state):
        logits, value = self(state)
        action = self.action_distribution.predict(logits)
        return np.squeeze(action, axis=-1), np.squeeze(value, axis=-1)