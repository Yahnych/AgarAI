"""
File: extractors
Date: 5/7/19 
Author: Jon Deaton (jdeaton@stanford.edu)
"""

import numpy as np
from gym_agario.envs.FullEnv import FullObservation


class GridFeatureExtractor:

    def __init__(self, view_size, grid_size, arena_size,
                 cells=True, others=True, viruses=True, food=False,
                 flat=False):
        self.view_size = view_size
        self.grid_size = grid_size

        # the size of each little square in the grid
        self.box_size = view_size / grid_size

        self.arena_size = arena_size
        self.flat = flat

        self.cells = cells
        self.viruses = viruses
        self.others = others
        self.foods = food

        self.depth = 1 + int(cells) + int(others) + int(viruses) + int(food)
        self.shape = (self.depth, grid_size, grid_size,)

        if flat:
            self.shape = tuple(np.prod(self.shape))

    def __call__(self, observation: FullObservation):
        return self.extract(observation)

    def extract(self, observation: FullObservation):
        agent = observation.agent
        loc = position(agent)
        if loc is None: return None  # no player position

        features = np.zeros(self.shape)

        self.add_entities_to_grid(features[0].view(), observation.pellets, loc)

        i = 1
        if self.cells:
            self.add_entities_to_grid(features[i].view(), observation.agent, loc)
            i += 1

        if self.others:
            for other in observation.others:
                self.add_entities_to_grid(features[i].view(), other, loc)
            i += 1

        if self.viruses:
            self.add_entities_to_grid(features[i].view(), observation.viruses, loc)
            i += 1

        if self.foods:
            self.add_entities_to_grid(features[i].view(), observation.foods, loc)
            i += 1

        if self.flat:
            return features.flatten()

        return features

    def add_entities_to_grid(self, arr, entities, loc):
        self.add_ones(loc, entities, arr)
        self.add_out_of_bounds(loc, arr)

    def add_ones(self, loc, entities, entity_features):
        for entity in entities:
            grid_x = int((entity[0] - loc[0]) / self.box_size) + self.grid_size // 2
            grid_y = int((entity[1] - loc[1]) / self.box_size) + self.grid_size // 2
            value = 1 if len(entity) <= 2 else entity[-1]

            if 0 <= grid_x < self.grid_size and 0 <= grid_y < self.grid_size:
                entity_features[grid_x][grid_y] += value

    def add_out_of_bounds(self, loc, entity_features, sentinel_value=-1):
        """ adds sentinel_value to out of bounds locations """
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                x_diff = i - int(self.grid_size / 2)
                y_diff = j - int(self.grid_size / 2)

                x_loc = x_diff * self.box_size + loc[0]
                y_loc = y_diff * self.box_size + loc[1]

                # if in bounds, increment
                if not (0 <= x_loc < self.arena_size and 0 <= y_loc < self.arena_size):
                    entity_features[i][j] = sentinel_value


class FeatureExtractor:

    def __init__(self, num_pellet=50, num_virus=5, num_food=10, num_other=5, num_cell=15):
        self.num_pellet = num_pellet
        self.num_virus  = num_virus
        self.num_food   = num_food
        self.num_other  = num_other
        self.num_cell   = num_cell

        self.size = 2 * num_pellet + 2 * num_virus + 2 * num_food + 5 * (1 + num_other) * num_cell
        self.shape = (self.size, )
        self.filler_value = -1000

    def __call__(self, observation: FullObservation):
        return self.extract(observation)

    def extract(self, observation: FullObservation):
        """ extracts features from an observation into a fixed-size feature vector
        :param observation: a named tuple Observation object
        :return: fixed length vector of extracted features about the observation
        """
        agent = observation.agent
        loc = position(agent)
        if loc is None: return None # no player position

        pellet_features = get_entity_features(loc, observation.pellets, self.num_pellet)
        virus_features =  get_entity_features(loc, observation.viruses, self.num_virus)
        food_features =   get_entity_features(loc, observation.foods, self.num_food)

        agent_cells = largest_cells(agent, n=self.num_cell)
        agent_cell_features = get_entity_features(loc, agent_cells, self.num_cell, relative=False)

        players_features = list()
        close_players = closest_players(loc, observation.others, n=self.num_other)
        for player in close_players:
            player_cells = largest_cells(player, n=self.num_cell)
            player_features = get_entity_features(loc, player_cells, self.num_cell)
            players_features.append(player_features)

        # there might not be enough players at all, so just pad the rest
        while len(players_features) < self.num_other:
            empty_fts = empty_features(self.num_cell, 5, filler_value=self.filler_value)
            players_features.append(empty_fts)

        feature_stacks = [pellet_features, virus_features, food_features, agent_cell_features]
        feature_stacks.extend(players_features)

        flattened = list(map(lambda arr: arr.flatten(), feature_stacks))
        features = np.hstack(flattened)
        np.nan_to_num(features, copy=False)
        return features


class ScreenFeatureExtractor:
    def __init__(self, num_frames, screen_len):
        self.screen_len = screen_len
        self.shape = (num_frames, screen_len, screen_len)

    def __call__(self, observation):
        return self.extract(observation)

    def extract(self, observation):
        assert isinstance(observation, np.ndarray)

        # average over color channels => to black and white
        return observation.mean(axis=-1)




# ======== utility functions =================

def get_entity_features(loc, entities, n, relative=True):
    _, ft_size = entities.shape
    entity_features = np.zeros((n, ft_size))
    close_entities = sort_by_proximity(loc, entities, n=n)
    if relative:
        to_relative_pos(close_entities, loc)
    num_close, _ = close_entities.shape
    entity_features[:num_close] = close_entities
    return entity_features

def largest_cells(player, n=None):
    order =  np.argsort(player[:, -1], axis=0)
    return player[order[:n]]

def closest_players(loc, others, n=None):
    distances = list()
    for player in others:
        location = position(player)
        distance = np.linalg.norm(loc - location) if location is not None else np.inf
        distances.append(distance)
    order = np.argsort(distances)
    return [others[i] for i in order[:n]]

def sort_by_proximity(loc, entities, n=None):
    positions = entities[:, (0, 1)]
    order = np.argsort(np.linalg.norm(positions - loc, axis=1))
    return entities[order[:n]]

def to_relative_pos(entities, loc):
    entities[:, (0, 1)] -= loc

def empty_features(n, dim, filler_value=0):
    fts = np.ones((n, dim))
    fts[:] = filler_value
    return fts

def position(player: np.ndarray):
    # weighted average of cell positions by mass
    if player.size == 0 or player[:, -1].sum == 0:
        return None

    loc = np.average(player[:, (0, 1)], axis=0, weights=player[:, -1])
    return loc
