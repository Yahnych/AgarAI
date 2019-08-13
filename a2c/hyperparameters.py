"""
File: hyperparameters
Date: 2019-07-25 
Author: Jon Deaton (jdeaton@stanford.edu)
"""

import json
import math

from a2c.Model import CNNEncoder, DenseEncoder


class HyperParameters(object):
    """ Simple class for storing model hyper-parameters """

    def __init__(self):
        self.seed = 42

        # to fill in by sub_classes
        self.env_name = None
        self.EncoderClass = None
        self.action_shape = None

        self.num_envs = 4

        # optimizer
        self.learning_rate = None

        self.gamma = None
        self.entropy_weight = None
        self.action_shape = None
        self.batch_size = None

    def override(self, params):
        """
        Overrides attributes of this object with those of "params".
        All attributes of "params" which are also attributes of this object will be set
        to the values found in "params". This is particularly useful for over-riding
        hyper-parameters from command-line arguments
        :param params: Object with attributes to override in this object
        :return: None
        """
        for attr in vars(params):
            if hasattr(self, attr) and getattr(params, attr) is not None:
                value = getattr(params, attr)
                setattr(self, attr, value)

    def save(self, file):
        """ save the hyper-parameters to file in JSON format """
        with open(file, 'w') as f:
            json.dump(self.__dict__, f, indent=4)

    @staticmethod
    def restore(file):
        """ restore hyper-parameters from JSON file """
        with open(file, 'r') as f:
            data = json.load(f)
        hp = HyperParameters()
        hp.__dict__.update(data)
        return hp


class CartPoleHyperparameters(HyperParameters):
    def __init__(self):
        super(CartPoleHyperparameters, self).__init__()

        self.env_name = "CartPole-v1"
        self.EncoderClass = DenseEncoder

        self.num_envs = 128
        self.learning_rate = 0.05
        self.action_shape = (2, )
        self.episode_length = 500
        self.entropy_weight = 1e-4


class HalfCheetahHyperparameters(HyperParameters):
    def __init__(self):
        super(HalfCheetahHyperparameters, self).__init__()

        self.env_name = "CartPole-v1"
        self.EncoderClass = DenseEncoder

        self.num_envs = 8
        self.learning_rate = 0.001
        self.action_shape = (7, )
        self.episode_length = 1024
        self.entropy_weight = 0.1


class GridEnvHyperparameters(HyperParameters):
    def __init__(self):
        super(GridEnvHyperparameters, self).__init__()

        self.env_name = "agario-grid-v0"

        self.EncoderClass = CNNEncoder

        self.learning_rate = 0.001
        self.num_episodes = 128
        self.gamma = 0.95
        self.batch_size = 256

        self.num_envs = 4

        self.entropy_weight = 1e-4

        self.action_shape = (16, 1, 1)
        self.episode_length = 1024

        # Agario Game parameters
        self.difficulty = "normal"
        self.ticks_per_step = 4  # set equal to 1 => bug
        self.arena_size = 500
        self.num_pellets = 1000
        self.num_viruses = 25
        self.num_bots = 25
        self.pellet_regen = True

        # observation parameters
        self.num_frames = 1
        self.grid_size = 16
        self.observe_pellets = True
        self.observe_viruses = True
        self.observe_cells   = True
        self.observe_others  = True

