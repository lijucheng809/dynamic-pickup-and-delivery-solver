from rectpack import newPacker
from copy import deepcopy
import sys

from simulator.dpdp_competition.algorithm.src.constrains.constrains_base import ConstrainsBase
from simulator.dpdp_competition.algorithm.src.common.vehicle import Vehicle
from simulator.dpdp_competition.algorithm.src.enum.demand_type_enum import DemandTypeEnum


class BinPackingConstrains(ConstrainsBase):
    def __init__(self, vehicle: Vehicle,
                 check_route_index_start: int,
                 check_route_index_end: int,
                 requests: dict):
        self.__vehicle = vehicle
        self.__check_route_index_start = check_route_index_start
        self.__check_route_index_end = check_route_index_end
        self.__requests = requests
        self.__route = self.__vehicle.getCurrentRoute

    def __rectangles_match(self, vehicle_dimension, route_index, delivery_only_id_bin_map: dict):
        rectangles = []
        current_rectangles_map = {}
        vehicle_rectangles = []
        for i in range(route_index+1):
            request_id = self.__route[i].requestID
            if self.__route[i].demandType == DemandTypeEnum.pickup.name:
                current_rectangles_map[request_id] = self.__requests[request_id]
            else:
                if request_id in current_rectangles_map:
                    current_rectangles_map.pop(request_id)
        for request_id, bins in current_rectangles_map.items():
            for bin in bins:
                rectangles.append((bin[0], bin[1]))
        for request_id, bin_dimensions in delivery_only_id_bin_map.items():
            for bin_dimension in bin_dimensions:
                rectangles.append((bin_dimension[0], bin_dimension[1]))
        for i in range(len(rectangles)):
            vehicle_rectangles.append((vehicle_dimension[0], vehicle_dimension[1]))
        packer = newPacker()
        for rectangle in rectangles:
            packer.add_rect(*rectangle)
        for vehicle_rectangle in vehicle_rectangles:
            packer.add_bin(*vehicle_rectangle)
        packer.pack()
        if len(packer) > 1:
            return False
        else:
            return True

    def isFeasible(self) -> bool:
        # todo 考虑装箱顺序的逻辑待实现，比如已放置好的箱子不可以挪动位置
        vehicle_dimension = self.__vehicle.get_vehicle_dimension
        delivery_only_id_bin_map = deepcopy(self.__vehicle.get_delivery_only_id_bin_map)
        for i in range(self.__check_route_index_start, self.__check_route_index_end+1):
            if self.__route[i].demandType != DemandTypeEnum.delivery.name \
                    or self.__route[i].demandType != DemandTypeEnum.delivery_only.name:
                if not self.__rectangles_match(vehicle_dimension, i, delivery_only_id_bin_map):
                    return False
            elif self.__route[i].demandType == DemandTypeEnum.delivery_only.name:
                delivery_only_id_bin_map.pop(self.__route[i].requestID)
        return True
