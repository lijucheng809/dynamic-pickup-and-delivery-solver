from abc import ABCMeta, abstractmethod
from copy import deepcopy
from typing import Dict
from datetime import datetime

from simulator.dpdp_competition.algorithm.src.requestPool import RequestPool
from simulator.dpdp_competition.algorithm.src.customer import Customer
from simulator.dpdp_competition.algorithm.src.vehicle import Vehicle
from simulator.dpdp_competition.algorithm.src.Operator import GreedyInsertionOperator, RegretInsertionOperator
from simulator.dpdp_competition.algorithm.conf.configs import configs


class Constructor(metaclass=ABCMeta):

    @abstractmethod
    def solve(self):
        pass

    @abstractmethod
    def outputSolution(self):
        pass


class SolomonInsertionHeuristic(Constructor):
    def __init__(self,
                 vehicles: Dict[str, Vehicle],
                 requests: RequestPool,
                 customers: Dict[str, Customer],
                 travelCost_Solver):
        self._vehicles = deepcopy(vehicles)
        self._requests = deepcopy(requests)
        self._customers = deepcopy(customers)
        self._insertionOperator = GreedyInsertionOperator(self._vehicles,
                                                          self._requests,
                                                          self._customers,
                                                          travelCost_Solver)

    def solve(self,
              time2Go=datetime.strptime(configs.date + " 0:0:0", "%Y-%m-%d %H:%M:%S"),
              CPU_limit=10.):

        if self._insertionOperator.insert(time2Go=time2Go, CPU_limit=CPU_limit):
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
