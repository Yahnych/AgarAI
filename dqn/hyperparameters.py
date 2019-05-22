"""
File: hyperparameters
Date: 5/6/19 
Author: Jon Deaton (jdeaton@stanford.edu)
"""

import json
import math


class HyperParameters(object):
    """ Simple class for storing model hyper-parameters """

    def __init__(self):
        self.seed = 42

        # to fill in by sub_classes
        self.env_name = None
        self.encoder_type = None

        # Agario Game parameters
        self.frames_per_step = 4
        self.arena_size = 10
        self.num_pellets = 1
        self.num_viruses = 0
        self.num_bots = 0
        self.pellet_regen = True

        self.action_shape = (4, 1, )

        self.episode_length = 100
        self.num_episodes = 10000
        self.p_dropout = 0.05
        self.gamma = 0.99

        # DQN parameters
        self.double_dqn = True
        self.dueling_dqn = True

        self.batch_size = 32
        self.replay_memory_capacity = 500
        self.lean_freq = 16
        self.target_update_freq = 128

        self.epsilon_base = 0.25
        self.epsilon_end = 0.0
        self.epsilon_decay = math.log(2) / 500

        # Adam Optimization parameters
        self.lr = 0.001
        self.adam_betas = (0.9, 0.999)
        self.adam_eps = 1e-8
        self.grad_clip_norm = 1

    def override(self, params):
        """
        Overrides attributes of this object with those of "params".
        All attributes of "params" which are also attributes of this object will be set
        to the values found in "params". This is particularly useful for over-riding
        hyperparamers from command-line arguments
        :param settings: Object with attributes to override in this object
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


class FullEnvHyperparameters(HyperParameters):
    def __init__(self):
        super(FullEnvHyperparameters, self).__init__()

        self.env_name = "agario-full-v0"

        self.num_pellets_features = 1
        self.num_viruses_features = 0
        self.num_food_features    = 0
        self.num_other_features   = 0
        self.num_cell_features    = 1

        # Network parameters
        self.encoder_type = 'linear'
        self.layer_sizes = [16, 16]


class ScreenEnvHyperparameters(HyperParameters):
    def __init__(self):
        super(ScreenEnvHyperparameters, self).__init__()

        self.env_name = "agario-screen-v0"
        self.encoder_type = 'cnn'
        self.screen_len = 128

        self.feature_extractor = None