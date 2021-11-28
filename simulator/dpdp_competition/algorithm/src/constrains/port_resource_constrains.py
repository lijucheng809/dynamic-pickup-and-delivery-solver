from datetime import datetime
from copy import deepcopy

from simulator.dpdp_competition.algorithm.src.constrains.constrains_base import ConstrainsBase
from simulator.dpdp_competition.algorithm.src.common.vehicle import Vehicle


class PortResourceConstrains(ConstrainsBase):
    def __init__(self, customers: dict, vehicle: Vehicle, customer_id: str, demand_type: str,
                 vehicle_arrive_time: datetime, request: dict,  node_index_in_route: int):
        self.__vehicle = vehicle
        self.__demand_type = demand_type
        self.__vehicle_arrive_time = vehicle_arrive_time
        self.__request = deepcopy(request)
        self.__node_index_in_route = node_index_in_route
        self.__customer_id = customer_id
        self.__customers = customers

    def isFeasible(self) -> bool:
        if not self.__vehicle.feasibleInsertion(customers=self.__customers,
                                                customer_id=self.__customer_id,
                                                demand_type=self.__demand_type,
                                                vehicle_arrive_time=self.__vehicle_arrive_time,
                                                request=self.__request,
                                                node_index_in_route=self.__node_index_in_route):
            return False
        else:
            return True
