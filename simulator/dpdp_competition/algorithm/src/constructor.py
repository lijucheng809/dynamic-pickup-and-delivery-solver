from abc import ABCMeta, abstractmethod
from copy import deepcopy
from typing import Dict
from datetime import datetime

from simulator.dpdp_competition.algorithm.src.requestPool import requestPool
from simulator.dpdp_competition.algorithm.src.customer import customer
from simulator.dpdp_competition.algorithm.src.vehicle import vehicle
from simulator.dpdp_competition.algorithm.src.Operator import GreedyInsertionOperator, RegretInsertionOperator

import simulator.dpdp_competition.algorithm.src.getConfig
gConfig = simulator.dpdp_competition.algorithm.src.getConfig.get_config()


class constructor(metaclass=ABCMeta):

    @abstractmethod
    def solve(self):
        pass

    @abstractmethod
    def outputSolution(self):
        pass


class solomonInsertionHeuristic(constructor):
    def __init__(self,
                 vehicles: Dict[str, vehicle],
                 requests: requestPool,
                 customers: Dict[str, customer],
                 travelCost_Solver):
        self._vehicles = deepcopy(vehicles)
        self._requests = deepcopy(requests)
        self._customers = deepcopy(customers)
        self._insertionOperator = GreedyInsertionOperator(self._vehicles,
                                                          self._requests,
                                                          self._customers,
                                                          travelCost_Solver)

    def solve(self, time2Go=datetime.strptime(gConfig["date"] + " 0:0:0", "%Y-%m-%d %H:%M:%S")):

        if self._insertionOperator.insert(time2Go=time2Go):
            return True
        else:
            return False

    @property
    def get_fail_insertion_requests(self):
        return self._insertionOperator.get_fail_insertion_requests

    @property
    def outputSolution(self):
        return self._insertionOperator.outputSolution()


if __name__ == "__main__":
    pass
