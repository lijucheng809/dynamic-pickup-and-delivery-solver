import random
import time
from abc import ABCMeta, abstractmethod
from typing import Dict
from datetime import datetime
import numpy as np
from copy import deepcopy
import sys
from queue import PriorityQueue

from simulator.dpdp_competition.algorithm.src.common.vehicle import Vehicle
from simulator.dpdp_competition.algorithm.src.common.source_pool import SourcePool
from simulator.dpdp_competition.algorithm.src.common.customer_request_combination import CustomerRequestCombination
from simulator.dpdp_competition.algorithm.src.common.request_pool import RequestPool
from simulator.dpdp_competition.algorithm.src.common.customer import Customer
from simulator.dpdp_competition.algorithm.conf.configs import Configs
from simulator.dpdp_competition.algorithm.src.constrains.capacity_constrains import CapacityConstrains
from simulator.dpdp_competition.algorithm.src.constrains.time_window_constrains import TimeWindowConstrains
from simulator.dpdp_competition.algorithm.src.constrains.lifo_constrains import LIFOConstrains
from simulator.dpdp_competition.algorithm.src.constrains.port_resource_constrains import PortResourceConstrains
from simulator.dpdp_competition.algorithm.src.enum.constrain_enum import ConstrainEnum
from simulator.dpdp_competition.algorithm.src.constrains.bin_packing_constrains import BinPackingConstrains
from simulator.dpdp_competition.algorithm.src.constrains.incompatible_constrains import VehicleItemCompatibleConstrain, \
    ItemCompatibleConstrain
from simulator.dpdp_competition.algorithm.src.utils.route_cost_util import route_cost
from simulator.dpdp_competition.algorithm.src.enum.request_info_enum import RequestInfoEnum
from simulator.dpdp_competition.algorithm.src.enum.route_cost_enum import RouteCostEnum
from simulator.dpdp_competition.algorithm.src.enum.demand_info_enum import DemandInfoEnum
from simulator.dpdp_competition.algorithm.src.enum.demand_type_enum import DemandTypeEnum


class InsertOperator(metaclass=ABCMeta):

    @abstractmethod
    def insert(self):
        pass

    @abstractmethod
    def outputSolution(self):
        pass


class RemoveOperator(metaclass=ABCMeta):

    @abstractmethod
    def remove(self, remove_number: int):
        pass


class LocalSearchOperator(metaclass=ABCMeta):

    @abstractmethod
    def move(self):
        pass


class ShawRemovalOperator(RemoveOperator):
    def __init__(self, vehicles: Dict[str, Vehicle]):
        self._vehicles = vehicles
        # 对到达时间和货量进行normalized
        min_arriveTime = np.infty
        max_arriveTime = -np.infty
        min_volume = np.infty
        max_volume = -np.infty
        startTime = datetime.strptime(Configs.date + " " + Configs.time, "%Y-%m-%d %H:%M:%S")
        for vehicleID in self._vehicles:
            if len(self._vehicles[vehicleID].getCurrentRoute) > 1:
                for i in range(1, len(self._vehicles[vehicleID].getCurrentRoute)):
                    node = self._vehicles[vehicleID].getCurrentRoute[i]
                    min_arriveTime = min(min_arriveTime, (node.vehicleArriveTime - startTime).seconds)
                    max_arriveTime = max(max_arriveTime, (node.vehicleArriveTime - startTime).seconds)
                    if node.demandType == "pickup":
                        min_volume = min(min_volume, node.volume)
                        max_volume = max(max_volume, node.volume)
        for vehicleID in self._vehicles:
            if len(self._vehicles[vehicleID].getCurrentRoute) > 1:
                for i in range(1, len(self._vehicles[vehicleID].getCurrentRoute)):
                    node = self._vehicles[vehicleID].getCurrentRoute[i]
                    arriveTime_normal = ((node.vehicleArriveTime - startTime).seconds - min_arriveTime) \
                                        / (max_arriveTime - min_arriveTime)
                    self._vehicles[vehicleID].getCurrentRoute[i].setNormalArriveTime(arriveTime_normal)
                    if node.demandType == "pickup":
                        if max_volume == min_volume:
                            volume_normal = 1
                        else:
                            volume_normal = (node.volume - min_volume) / (max_volume - min_volume)
                        self._vehicles[vehicleID].getCurrentRoute[i].setNormalVolume(volume_normal)

    @staticmethod
    def _relatedness(request_1: CustomerRequestCombination,
                     request_2: CustomerRequestCombination):
        """
        两个request应该都是pickup点
        :param request_1:
        :param request_2:
        :return: relatedness value
        """
        assert request_1.demandType == "pickup" or request_2.demandType == "pickup"
        distance_p1_p2 = route_cost.getTravelCost(request_1.customerID, request_2.customerID)["normal_distance"]
        distance_d1_d2 = route_cost.getTravelCost(request_1.brotherNode.customerID,
                                                  request_2.brotherNode.customerID)["normal_distance"]
        diff_arriveTime_p1_p2 = abs(request_1.vehicleArriveTime_normal - request_2.vehicleArriveTime_normal)
        diff_arriveTime_d1_d2 = abs(request_1.brotherNode.vehicleArriveTime_normal
                                    - request_2.brotherNode.vehicleArriveTime_normal)
        diff_volume_p1_p2 = abs(request_1.volume_normal - request_2.volume_normal)

        distance_weight = Configs.shaw_removal_distance_weight
        travelTime_weight = Configs.shaw_removal_travel_time_weight
        demand_weight = Configs.shaw_removal_demand_weight
        R = distance_weight * (distance_d1_d2 + distance_p1_p2) \
            + travelTime_weight * (diff_arriveTime_d1_d2 + diff_arriveTime_p1_p2) \
            + demand_weight * diff_volume_p1_p2
        return R

    def getPickupNode(self):
        pickupNodes = dict()
        for vehicleID in self._vehicles:
            if len(self._vehicles[vehicleID].getCurrentRoute) > 1:
                for i in range(1, len(self._vehicles[vehicleID].getCurrentRoute)):
                    node = self._vehicles[vehicleID].getCurrentRoute[i]
                    if node.demandType == "pickup":
                        pickupNodes[node] = vehicleID
        return pickupNodes

    def remove(self, remove_number: int):
        removals = dict()

        pickupNodes = self.getPickupNode()
        randomSelectNode = random.choice(list(pickupNodes.keys()))
        unSelectNodes = dict()
        for node in pickupNodes:
            if node != randomSelectNode:
                unSelectNodes[node] = pickupNodes[node]
            else:
                removals[node] = pickupNodes[node]
        while len(removals) < remove_number:
            node1 = random.choice(list(removals.keys()))
            node_R_map = dict()
            for node2 in unSelectNodes:
                R = self._relatedness(node1, node2)
                node_R_map[node2] = R
            node_R_map = sorted(node_R_map.items(), key=lambda x: x[1], reverse=False)
            random_index = int(
                np.power(np.random.rand(), Configs.shaw_removal_randomness_value) * (len(node_R_map) - 1))
            node_new = node_R_map[random_index][0]
            removals[node_new] = unSelectNodes[node_new]
            unSelectNodes.pop(node_new)
        return removals


class RandomRemovalOperator(ShawRemovalOperator):
    def __init__(self, vehicles: Dict[str, Vehicle]):
        self._vehicles = vehicles

    def remove(self, remove_number: int):
        removals = dict()
        pickupNodes = self.getPickupNode()
        randomSelectNode = random.sample((list(pickupNodes.keys())), remove_number)
        for node in randomSelectNode:
            removals[node] = pickupNodes[node]
        return removals


class WorstRemovalOperator(RemoveOperator):
    def __init__(self, vehicles: Dict[str, Vehicle]):
        self._initVehicles = vehicles
        self._vehicles = deepcopy(vehicles)
        self._pickupNode = dict()
        self._pickupNodeIndex = dict()  # 存储对应入参的vehicles的实际位置，因为deepcopy之后node无法作为对应原始vehicles的key值
        self._travelCost_solver = route_cost
        for vehicleID in self._vehicles:
            if len(self._vehicles[vehicleID].getCurrentRoute) > 1:
                for node in self._vehicles[vehicleID].getCurrentRoute:
                    if node.demandType == "pickup":
                        self._pickupNode[node] = vehicleID
                        route_index = self._vehicles[vehicleID].getCurrentRoute.index(node)
                        self._pickupNodeIndex[node] = {"vehicle": vehicleID, "routeIndex": route_index}
                    else:
                        continue

    def _getDifferentCost(self, pickup_node: CustomerRequestCombination):
        assert pickup_node.demandType == "pickup"
        delivery_node = pickup_node.brotherNode
        pickup_node_index = self._vehicles[pickup_node.vehicleID].getCurrentRoute.index(pickup_node)
        delivery_node_index = self._vehicles[delivery_node.vehicleID].getCurrentRoute.index(delivery_node)
        vehicle = deepcopy(self._vehicles[pickup_node.vehicleID])
        old_cost = deepcopy(vehicle.getCurrentRouteCost)

        pickup_node_new = vehicle.getCurrentRoute[pickup_node_index]
        delivery_node_new = vehicle.getCurrentRoute[delivery_node_index]
        vehicle.getCurrentRoute.remove(pickup_node_new)
        vehicle.getCurrentRoute.remove(delivery_node_new)
        vehicle.updateTravelCost()
        new_cost = deepcopy(vehicle.getCurrentRouteCost)
        return old_cost - new_cost

    def _removeNodeFromRoute(self, pickup_node: CustomerRequestCombination):
        assert pickup_node.demandType == "pickup"
        delivery_node = pickup_node.brotherNode
        self._vehicles[pickup_node.vehicleID].getCurrentRoute.remove(pickup_node)
        self._vehicles[pickup_node.vehicleID].getCurrentRoute.remove(delivery_node)
        self._vehicles[pickup_node.vehicleID].updateTravelCost()

    def remove(self, remove_number: int):
        removals = dict()
        while remove_number > 0:
            node_cost_map = dict()
            for node in self._pickupNode:
                if node.demandType == "pickup":
                    node_cost_map[node] = self._getDifferentCost(node)
                else:
                    continue
            node_cost_map = sorted(node_cost_map.items(), key=lambda x: x[1], reverse=True)
            random_index = int(
                np.power(np.random.rand(), Configs.worst_removal_randomness_value) * (len(node_cost_map) - 1))
            node_new = node_cost_map[random_index][0]
            indexes = self._pickupNodeIndex[node_new]
            node_new1 = self._initVehicles[indexes["vehicle"]].getCurrentRoute[indexes["routeIndex"]]
            removals[node_new1] = self._pickupNode[node_new]
            # removals[node_new] = self._pickupNode[node_new]
            self._removeNodeFromRoute(node_new)
            self._pickupNode.pop(node_new)
            remove_number -= 1
        return removals


class GreedyInsertionOperator(InsertOperator):
    def __init__(self,
                 vehicles: Dict[str, Vehicle],
                 requests: RequestPool,
                 customers: Dict[str, Customer]):
        self.__source_pool = SourcePool(vehicles, customers, requests)
        if Configs.constrains[ConstrainEnum.port_resource]:
            for customerID in self.__source_pool.customers:
                self.__source_pool.customers[customerID].gen_node_port_map()
        self.__travelCost_solver = route_cost
        self.__fail_insertion_requests = []

    @property
    def get_fail_insertion_requests(self):
        return self.__fail_insertion_requests

    def _vehicle_customer_match(self):
        for vehicleID in self.__source_pool.vehicles:
            length = len(self.__source_pool.vehicles[vehicleID].getCurrentRoute)
            if length > 1:
                for index, node in enumerate(self.__source_pool.vehicles[vehicleID].getCurrentRoute):
                    if node.requestID != 0:
                        customer_object = self.__source_pool.customers[node.customerID]
                        customer_object.getDispatchedRequestSet[node.requestID] = node
                        if node.requestID in customer_object.get_node_port_map:
                            port_index = customer_object.get_node_port_map[node.requestID]
                            customer_object.getCurrentPortStatus[port_index[0]][port_index[1]] = node

    def _getResource(self):
        minpq_unDispatched_request = PriorityQueue()
        available_vehicleID_set = []
        # print(self._source_pool.requests.getUnDispatchedPool)
        for requestID in self.__source_pool.requests.getUnDispatchedPool:
            creation_time = self.__source_pool.requests.getUnDispatchedPool[requestID][RequestInfoEnum.creation_time.name]
            minpq_unDispatched_request.put((creation_time, requestID))
        for vehicleID in self.__source_pool.vehicles:
            if self.__source_pool.vehicles[vehicleID].getStatus == "busy" or self.__source_pool.vehicles[
                vehicleID].getStatus == "idle":
                available_vehicleID_set.append(vehicleID)
            else:
                continue

        # random.shuffle(available_vehicleID_set)
        return available_vehicleID_set, minpq_unDispatched_request

    def _get_insert_cost(self, vehicle_id, route_length, pickup_route_index, delivery_route_index, pickup_customer_id,
                         delivery_customer_id):
        route = self.__source_pool.vehicles[vehicle_id].getCurrentRoute
        travel_const1 = self.__travelCost_solver.getTravelCost(route[pickup_route_index - 1].customerID,
                                                               pickup_customer_id)
        if pickup_route_index == route_length:
            travel_const2 = self.__travelCost_solver.getTravelCost(pickup_customer_id,
                                                                   delivery_customer_id)
            insert_cost = travel_const1[RouteCostEnum.distance.name] + travel_const2[RouteCostEnum.distance.name]
        elif pickup_route_index < route_length and delivery_route_index == route_length + 1:
            travel_const2 = self.__travelCost_solver.getTravelCost(pickup_customer_id,
                                                                   route[pickup_route_index + 1].customerID)
            travel_const3 = self.__travelCost_solver.getTravelCost(route[pickup_route_index - 1].customerID,
                                                                   route[pickup_route_index + 1].customerID)
            travel_const4 = self.__travelCost_solver.getTravelCost(route[delivery_route_index - 1].customerID,
                                                                   delivery_customer_id)
            insert_cost = travel_const1[RouteCostEnum.distance.name] + travel_const2[RouteCostEnum.distance.name] \
                          - travel_const3[RouteCostEnum.distance.name] + travel_const4[RouteCostEnum.distance.name]
        else:
            travel_const2 = self.__travelCost_solver.getTravelCost(pickup_customer_id,
                                                                   route[pickup_route_index + 1].customerID)
            travel_const3 = self.__travelCost_solver.getTravelCost(route[pickup_route_index - 1].customerID,
                                                                   route[pickup_route_index + 1].customerID)
            travel_const4 = self.__travelCost_solver.getTravelCost(route[delivery_route_index - 1].customerID,
                                                                   delivery_customer_id)
            travel_const5 = self.__travelCost_solver.getTravelCost(delivery_customer_id,
                                                                   route[delivery_route_index].customerID)
            travel_const6 = self.__travelCost_solver.getTravelCost(route[delivery_route_index - 1].customerID,
                                                                   route[delivery_route_index].customerID)

            insert_cost = travel_const1[RouteCostEnum.distance.name] + travel_const2[RouteCostEnum.distance.name] \
                          - travel_const3[RouteCostEnum.distance.name] + travel_const4[RouteCostEnum.distance.name] \
                          + travel_const5[RouteCostEnum.distance.name] - travel_const6[RouteCostEnum.distance.name]
        return insert_cost

    def _orderMatched(self, vehicleID, request):
        route = self.__source_pool.vehicles[vehicleID].getCurrentRoute
        pickup_customer_id = request[RequestInfoEnum.pickup_demand_info.name][DemandInfoEnum.customer_id.name]
        delivery_customer_id = request[RequestInfoEnum.delivery_demand_info.name][DemandInfoEnum.customer_id.name]
        requestID = request[RequestInfoEnum.requestID.name]
        if "-" in requestID:
            _index = requestID.index("-")
            requestID = requestID[:_index]
        pickup_flag = False
        delivery_flag = False
        pickup_route_index = None
        delivery_route_index = None
        for index, node in enumerate(route):
            if index == 0:
                continue
            if requestID in node.requestID:
                pickup_route_index = index + 1
                pickup_flag = True
                break
            if node.customerID == pickup_customer_id and not pickup_flag:
                if index < len(route) - 1 and "-" not in request[RequestInfoEnum.requestID.name] and "-" in node.requestID \
                        and "-" in route[index + 1].requestID:
                    index1, index2 = node.requestID.index("-"), route[index + 1].requestID.index("-")
                    if node.requestID[:index1] == route[index + 1].requestID[:index2]:
                        continue
                capacity_constrain = CapacityConstrains(request, self.__source_pool.vehicles[vehicleID], index)
                if not capacity_constrain.isFeasible():
                    continue
                time_window_constrain = TimeWindowConstrains(node, pickup_customer_id, DemandTypeEnum.pickup.name, request,
                                                             self.__travelCost_solver)

                if capacity_constrain.isFeasible() and time_window_constrain.isFeasible():
                    pickup_flag = True
                    pickup_route_index = index + 1

            if node.customerID == delivery_customer_id and not delivery_flag and pickup_flag:
                # delivery_flag = True
                delivery_route_index = index + 1
        return {"pickup_flag": pickup_flag,
                "delivery_flag": delivery_flag,
                "pickup_route_index": pickup_route_index,
                "delivery_route_index": delivery_route_index}

    def _PD_insertion(self, vehicleID, request, pickup_customer_id, delivery_customer_id, requestID, source_pool_temp,
                      best_score):
        """
        1、先插入pickup,再插入delivery，计算总的成本增加值
        2、服从last in first out原则
        """
        route_length = len(self.__source_pool.vehicles[vehicleID].getCurrentRoute)
        insertion_score_dict = {}
        for i in range(1, route_length + 1):
            route = self.__source_pool.vehicles[vehicleID].getCurrentRoute
            requestID_new = request[RequestInfoEnum.requestID.name]
            if "-" in requestID_new:
                _index = requestID_new.index("-")
                requestID_new = requestID_new[:_index]
            if 1 < i < route_length - 1 and requestID_new in route[i - 1].requestID and requestID_new in route[
                i + 1].requestID:
                continue
            if 1 < i < route_length - 1 and route[i - 1].customerID == route[i + 1].customerID:
                continue
            if 1 < i < route_length - 1 and "-" in route[i - 1].requestID and "-" in route[i + 1].requestID:
                index_1 = route[i - 1].requestID.index("-")
                index_2 = route[i + 1].requestID.index("-")
                if route[i - 1].requestID[:index_1] == route[i + 1].requestID[:index_2]:
                    continue
            # 容量约束
            capacity_constrain = CapacityConstrains(request, self.__source_pool.vehicles[vehicleID], i - 1)
            if not capacity_constrain.isFeasible():
                continue
            # pickup时间窗约束
            pickup_time_window_constrain = TimeWindowConstrains(route[i - 1], pickup_customer_id, DemandTypeEnum.pickup.name, request,
                                                                self.__travelCost_solver)

            if not pickup_time_window_constrain.isFeasible():
                continue
            # 排队等待约束
            port_resource_constrain = PortResourceConstrains(self.__source_pool.customers,
                                                             self.__source_pool.vehicles[vehicleID], pickup_customer_id,
                                                             DemandTypeEnum.pickup.name,
                                                             pickup_time_window_constrain.get_node_arrive_time,
                                                             request, i)
            if not port_resource_constrain.isFeasible():
                self.__source_pool = deepcopy(source_pool_temp)
                if Configs.constrains[ConstrainEnum.port_resource]:
                    self._vehicle_customer_match()
                continue

            insertion_score_dict_temp = self._delivery_insertion(
                i,
                route_length,
                pickup_customer_id,
                delivery_customer_id,
                request,
                requestID,
                vehicleID,
                source_pool_temp,
                best_score)
            if insertion_score_dict_temp:
                insertion_score_dict = insertion_score_dict_temp
                best_score = insertion_score_dict["score"]

        return insertion_score_dict

    def _delivery_insertion(self, pickup_route_index, route_length, pickup_customer_id, delivery_customer_id, request,
                            requestID, vehicleID, source_pool_temp, best_score):
        source_pool_temp1 = deepcopy(self.__source_pool)
        insertion_score_dict = {}
        for j in range(pickup_route_index + 1, route_length + 2):
            self.__source_pool = deepcopy(source_pool_temp1)
            if Configs.constrains[ConstrainEnum.port_resource]:
                self._vehicle_customer_match()
            route = self.__source_pool.vehicles[vehicleID].getCurrentRoute
            # delivery时间窗约束
            delivery_time_window_constrain = TimeWindowConstrains(route[j - 1], delivery_customer_id, DemandTypeEnum.delivery.name,
                                                                  request, self.__travelCost_solver)
            #     continue
            if not delivery_time_window_constrain.isFeasible():
                continue
            # last in first out 约束
            lifo_constrain = LIFOConstrains(self.__source_pool.vehicles[vehicleID], pickup_route_index, j)
            if not lifo_constrain.isFeasible():
                continue
            c11 = self._get_insert_cost(vehicleID, route_length, pickup_route_index, j, pickup_customer_id,
                                        delivery_customer_id)

            c11 += self._get_current_mileage(source_pool_temp.vehicles)
            if best_score < c11 or c11 == np.infty:
                continue

            # 排队等待约束

            port_resource_constrain = PortResourceConstrains(self.__source_pool.customers,
                                                             self.__source_pool.vehicles[vehicleID],
                                                             delivery_customer_id,
                                                             DemandTypeEnum.delivery.name,
                                                             delivery_time_window_constrain.get_node_arrive_time,
                                                             request, j)
            if not port_resource_constrain.isFeasible():
                self.__source_pool = deepcopy(source_pool_temp1)
                if Configs.constrains[ConstrainEnum.port_resource]:
                    self._vehicle_customer_match()
                continue
            self.__source_pool.vehicles[vehicleID].getCurrentRoute[pickup_route_index].setBrotherNode(
                self.__source_pool.vehicles[vehicleID].getCurrentRoute[j])
            self.__source_pool.vehicles[vehicleID].getCurrentRoute[j].setBrotherNode(
                self.__source_pool.vehicles[vehicleID].getCurrentRoute[pickup_route_index])

            if Configs.constrains[ConstrainEnum.bin_packing]:
                bin_packing_constrain = BinPackingConstrains(self.__source_pool.vehicles[vehicleID], pickup_route_index,
                                                             j, self.__source_pool.requests.get_request_id_dimension_map)
                if not bin_packing_constrain.isFeasible():
                    continue
            best_score = c11
            insertion_score_dict = {"score": best_score,
                                    "vehicleID": vehicleID,
                                    "requestID": requestID,
                                    "sourcePool": deepcopy(self.__source_pool)}
            if j < route_length + 1 and delivery_customer_id == route[j - 1].customerID:
                """这里的逻辑是，找到同批次装卸货的点，一定是cost最小的，所以没必要继续搜寻"""
                break
        self.__source_pool = deepcopy(source_pool_temp)
        if Configs.constrains[ConstrainEnum.port_resource]:
            self._vehicle_customer_match()
        return insertion_score_dict

    def insert(self,
               time2Go=datetime.strptime(Configs.date + " 0:0:0", "%Y-%m-%d %H:%M:%S"),
               tp="constructor",
               start_run_time=time.time(),
               CPU_limit=10) -> bool:
        if Configs.constrains[ConstrainEnum.port_resource]:
            self._vehicle_customer_match()
        available_vehicleID_set, minpq_unDispatched_request = self._getResource()
        while not minpq_unDispatched_request.empty():
            requestID = minpq_unDispatched_request.get()[1]
            request = self.__source_pool.requests.getUnDispatchedPool[requestID]
            # print("total requests:", minpq_unDispatched_request.qsize())
            # print("当前requestID:", requestID, "real request_id: ", request["requestID"], " creation_time:", request["creation_time"])
            # self.is_fake_route()
            source_pool_temp = deepcopy(self.__source_pool)
            insertion_flag = False  # 判断是否插入成功
            insertion_score_dict = dict()
            best_score = np.infty
            for vehicleID in available_vehicleID_set:
                if Configs.constrains[ConstrainEnum.incompatible_item_vehicle]:
                    if not VehicleItemCompatibleConstrain(
                            self.__source_pool.vehicles[vehicleID].get_compatible_item_type_list,
                            request[RequestInfoEnum.item_type.name]).isFeasible():
                        continue

                if Configs.constrains[ConstrainEnum.incompatible_items]:
                    if not ItemCompatibleConstrain(self.__source_pool.vehicle[vehicleID],
                                                   self.__source_pool.requests,
                                                   request[RequestInfoEnum.item_type.name]).isFeasible():
                        continue

                if time.time() - start_run_time > CPU_limit * 60:
                    return False
                pickup_customer_id = request[RequestInfoEnum.pickup_demand_info.name][DemandInfoEnum.customer_id.name]
                delivery_customer_id = request[RequestInfoEnum.delivery_demand_info.name][DemandInfoEnum.customer_id.name]
                if request[RequestInfoEnum.pickup_demand_info.name][DemandInfoEnum.volume.name] > self.__source_pool.vehicles[vehicleID].getCapacity:
                    """需求拆分"""
                    print("需求超过最大载重！！  ", requestID)
                    continue
                if len(self.__source_pool.vehicles[vehicleID].getCurrentRoute) == 1:  # 安排一辆空闲的车
                    """车辆从起始点出发"""
                    depot_node = self.__source_pool.vehicles[vehicleID].getCurrentRoute[0]
                    if depot_node.requestID == 0 and not depot_node.vehicleArriveTime:
                        self.__source_pool.vehicles[vehicleID].getCurrentRoute[0].setVehicleArriveTime(time2Go)
                        self.__source_pool.vehicles[vehicleID].getCurrentRoute[0].setVehicleDepartureTime(time2Go)
                    depot_id = self.__source_pool.vehicles[vehicleID].getDepotID
                    travel_cost_depot_2_pickup = self.__travelCost_solver.getTravelCost(depot_id, pickup_customer_id)
                    travel_cost_pickup2delivery = self.__travelCost_solver.getTravelCost(pickup_customer_id,
                                                                                         delivery_customer_id)
                    pickup_time_window_constrain = TimeWindowConstrains(depot_node, pickup_customer_id, DemandTypeEnum.pickup.name,
                                                                        request, self.__travelCost_solver)

                    if not pickup_time_window_constrain.isFeasible():
                        continue

                    c11 = travel_cost_depot_2_pickup[RouteCostEnum.distance.name] + travel_cost_pickup2delivery[RouteCostEnum.distance.name]
                    c11 += self._get_current_mileage(source_pool_temp.vehicles)
                    if best_score < c11:
                        continue
                    # 排队等待约束

                    port_resource_constrain = PortResourceConstrains(self.__source_pool.customers,
                                                                     self.__source_pool.vehicles[vehicleID],
                                                                     pickup_customer_id,
                                                                     DemandTypeEnum.pickup.name,
                                                                     pickup_time_window_constrain.get_node_arrive_time,
                                                                     request, 1)
                    if not port_resource_constrain.isFeasible():
                        self.__source_pool = deepcopy(source_pool_temp)
                        if Configs.constrains[ConstrainEnum.port_resource]:
                            self._vehicle_customer_match()
                        continue

                    pickupNode = self.__source_pool.vehicles[vehicleID].getCurrentRoute[1]
                    delivery_time_window_constrain = TimeWindowConstrains(pickupNode, delivery_customer_id, DemandTypeEnum.delivery.name,
                                                                          request, self.__travelCost_solver)
                    if not delivery_time_window_constrain.isFeasible():
                        self.__source_pool = deepcopy(source_pool_temp)
                        if Configs.constrains[ConstrainEnum.port_resource]:
                            self._vehicle_customer_match()
                        continue
                    # 排队等待约束

                    port_resource_constrain = PortResourceConstrains(self.__source_pool.customers,
                                                                     self.__source_pool.vehicles[vehicleID],
                                                                     delivery_customer_id,
                                                                     DemandTypeEnum.delivery.name,
                                                                     delivery_time_window_constrain.get_node_arrive_time,
                                                                     request, 2)
                    if not port_resource_constrain.isFeasible():
                        self.__source_pool = deepcopy(source_pool_temp)
                        if Configs.constrains[ConstrainEnum.port_resource]:
                            self._vehicle_customer_match()
                        continue
                    insertion_flag = True
                    self.__source_pool.vehicles[vehicleID].getCurrentRoute[1].setBrotherNode(
                        self.__source_pool.vehicles[vehicleID].getCurrentRoute[2])
                    self.__source_pool.vehicles[vehicleID].getCurrentRoute[2].setBrotherNode(
                        self.__source_pool.vehicles[vehicleID].getCurrentRoute[1])
                    best_score = c11
                    insertion_score_dict = {"score": best_score,
                                            "vehicleID": vehicleID,
                                            "requestID": requestID,
                                            "sourcePool": deepcopy(self.__source_pool)}
                    self.__source_pool = deepcopy(source_pool_temp)
                    if Configs.constrains[ConstrainEnum.port_resource]:
                        self._vehicle_customer_match()
                else:  # 在现有路线上插入需求
                    pd_insert_info = self._orderMatched(vehicleID, request)
                    route_length = len(self.__source_pool.vehicles[vehicleID].getCurrentRoute)
                    insert_feasible = False
                    if pd_insert_info["pickup_flag"]:
                        same_node = self.__source_pool.vehicles[vehicleID].getCurrentRoute[
                            pd_insert_info["pickup_route_index"] - 1]
                        port_resource_constrain1 = PortResourceConstrains(self.__source_pool.customers,
                                                                          self.__source_pool.vehicles[vehicleID],
                                                                          pickup_customer_id,
                                                                          DemandTypeEnum.pickup.name,
                                                                          same_node.vehicleArriveTime,
                                                                          request, pd_insert_info["pickup_route_index"])
                        if port_resource_constrain1.isFeasible():
                            insert_feasible = True
                            # todo pd_insert_info["delivery_flag"]恒为False, 待完善
                            if pd_insert_info["delivery_flag"]:
                                same_node = self.__source_pool.vehicles[vehicleID].getCurrentRoute[
                                    pd_insert_info["delivery_route_index"]]
                                port_resource_constrain2 = PortResourceConstrains(self.__source_pool.customers,
                                                                                  self.__source_pool.vehicles[vehicleID],
                                                                                  delivery_customer_id,
                                                                                  DemandTypeEnum.delivery.name,
                                                                                  same_node.vehicleArriveTime,
                                                                                  request,
                                                                                  pd_insert_info["delivery_route_index"])
                                if port_resource_constrain2.isFeasible():
                                    best_score = 0
                                    insertion_flag = True
                                    p_index = pd_insert_info["pickup_route_index"]
                                    d_index = pd_insert_info["delivery_route_index"] + 1
                                    self.__source_pool.vehicles[vehicleID].getCurrentRoute[p_index].setBrotherNode(
                                        self.__source_pool.vehicles[vehicleID].getCurrentRoute[d_index])
                                    self.__source_pool.vehicles[vehicleID].getCurrentRoute[d_index].setBrotherNode(
                                        self.__source_pool.vehicles[vehicleID].getCurrentRoute[p_index])
                                    if Configs.constrains[ConstrainEnum.bin_packing]:
                                        bin_packing_constrain = BinPackingConstrains(
                                            self.__source_pool.vehicles[vehicleID], p_index, d_index,
                                            self.__source_pool.requests.get_request_id_dimension_map)
                                        if not bin_packing_constrain.isFeasible():
                                            continue
                                    insertion_score_dict = {"score": best_score,
                                                            "vehicleID": vehicleID,
                                                            "requestID": requestID,
                                                            "sourcePool": deepcopy(self.__source_pool)}
                                else:
                                    self.__source_pool = deepcopy(source_pool_temp)
                                    if Configs.constrains[ConstrainEnum.port_resource]:
                                        self._vehicle_customer_match()
                                break
                            else:
                                insertion_score_dict_temp = self._delivery_insertion(
                                    pd_insert_info["pickup_route_index"],
                                    route_length,
                                    pickup_customer_id,
                                    delivery_customer_id,
                                    request,
                                    requestID,
                                    vehicleID,
                                    source_pool_temp,
                                    best_score)
                                if insertion_score_dict_temp:
                                    insertion_flag = True
                                    insertion_score_dict = insertion_score_dict_temp
                                    best_score = insertion_score_dict["score"]
                        else:
                            self.__source_pool = deepcopy(source_pool_temp)
                            if Configs.constrains[ConstrainEnum.port_resource]:
                                self._vehicle_customer_match()
                    if not insert_feasible:
                        insertion_score_dict_temp = self._PD_insertion(vehicleID, request, pickup_customer_id,
                                                                       delivery_customer_id, requestID,
                                                                       source_pool_temp, best_score)
                        if insertion_score_dict_temp:
                            insertion_flag = True
                            insertion_score_dict = insertion_score_dict_temp
                            best_score = insertion_score_dict["score"]

            if insertion_flag:
                """ 选择最优结果的那一辆车"""
                self.__source_pool = insertion_score_dict["sourcePool"]
                self.__source_pool.requests.updateDispatchedRequestPool(insertion_score_dict[RequestInfoEnum.requestID.name], "add")
                if Configs.constrains[ConstrainEnum.port_resource]:
                    self._vehicle_customer_match()

            else:
                """需求分配失败"""
                print("insertion fail requestID:", requestID,
                      " creation_time:", request[RequestInfoEnum.creation_time.name],
                      " real request_id", request[RequestInfoEnum.requestID.name],
                      " tw_right：", request[RequestInfoEnum.pickup_demand_info.name][DemandInfoEnum.time_window.name][1], file=sys.stderr)
                if tp == "heuristic":
                    return False
                self.__fail_insertion_requests.append({requestID:
                                                          self.__source_pool.requests.getUnDispatchedPool[requestID]})
                source_pool_temp.requests.getUnDispatchedPool.pop(requestID)
                self.__source_pool = deepcopy(source_pool_temp)
                if Configs.constrains[ConstrainEnum.port_resource]:
                    self._vehicle_customer_match()
        if self.__fail_insertion_requests:
            return False
        return True

    def _get_current_mileage(self, vehicles):
        score = 0
        for vehicleID in vehicles:
            vehicles[vehicleID].updateTravelCost()
            score += vehicles[vehicleID].getCurrentRouteCost
            score += vehicles[vehicleID].getMileage
        return score

    @property
    def getObjectiveScore(self):
        score = 0
        for vehicleID in self.__source_pool.vehicles:
            self.__source_pool.vehicles[vehicleID].updateTravelCost()
            score += self.__source_pool.vehicles[vehicleID].getCurrentRouteCost
            score += self.__source_pool.vehicles[vehicleID].getMileage
        return score

    def outputSolution(self):
        if Configs.constrains[ConstrainEnum.port_resource]:
            self._vehicle_customer_match()
        return self.__source_pool.vehicles, self.__source_pool.customers, self.__source_pool.requests


class RegretInsertionOperator(GreedyInsertionOperator):
    def __init__(self,
                 vehicles: Dict[str, Vehicle],
                 requests: RequestPool,
                 customers: Dict[str, Customer],
                 travelCost_solver,
                 degree=2):
        self._vehicles = deepcopy(vehicles)
        self._requests = deepcopy(requests)
        self._customers = deepcopy(customers)
        self._degree = degree
        self._travelCost_solver = travelCost_solver

    def __sorted_candidate(self, candidate_):
        candidate_ = sorted(candidate_, key=lambda x: x["score"])
        if len(candidate_) > self._degree:
            del candidate_[len(candidate_) - 1]

    def insert(self,
               time2Go=datetime.strptime(Configs.date + " 0:0:0", "%Y-%m-%d %H:%M:%S"),
               tp="constructor") -> bool:
        available_vehicleID_set, unDispatchedRequestsID_set = self._getResource()
        # print(unDispatchedRequestsID_set)
        unDispatchedRequestsID_num = len(unDispatchedRequestsID_set)
        insertion_fail_count = 0
        while len(unDispatchedRequestsID_set) > 0:
            insertion_flag = False  # 判断是否插入成功
            insertion_score_dict = dict()
            best_score = - np.infty
            random.shuffle(available_vehicleID_set)
            random.shuffle(unDispatchedRequestsID_set)
            for requestID in unDispatchedRequestsID_set:
                vehicles_temp = deepcopy(self._vehicles)
                requests_temp = deepcopy(self._requests)
                customers_temp = deepcopy(self._customers)
                candidate_ = []
                for vehicleID in available_vehicleID_set:
                    request = self._requests.getUnDispatchedPool[requestID]
                    pickup_customer_id = request["pickup_demand_info"]["customer_id"]
                    delivery_customer_id = request["delivery_demand_info"]["customer_id"]
                    if len(self._vehicles[vehicleID].getCurrentRoute) == 1:  # 安排一辆空闲的车
                        if request["pickup_demand_info"]["volume"] > self._vehicles[vehicleID].getCapacity:
                            """需求拆分"""
                            continue
                        """车辆从起始点出发"""
                        self._vehicles[vehicleID].getCurrentRoute[0].setVehicleArriveTime(time2Go)
                        self._vehicles[vehicleID].getCurrentRoute[0].setVehicleDepartureTime(time2Go)

                        depotNode = self._vehicles[vehicleID].getCurrentRoute[0]
                        depotID = self._vehicles[vehicleID].getDepotID
                        travel_cost_depot2pickup = self._travelCost_solver.getTravelCost(depotID, delivery_customer_id)
                        travel_cost_pickup2delivery = self._travelCost_solver.getTravelCost(pickup_customer_id,
                                                                                            delivery_customer_id)
                        pickup_tw_constrain = self._time_window_constrain(depotNode,
                                                                          pickup_customer_id,
                                                                          "pickup",
                                                                          request)
                        if not pickup_tw_constrain["feasible"]:
                            continue
                        c11 = travel_cost_depot2pickup["distance"] + travel_cost_pickup2delivery["distance"]
                        if len(candidate_) == self._degree:
                            if candidate_[self._degree - 1]["score"] < c11:
                                continue
                        if not self._insertion_constrain(vehicleID,
                                                         pickup_customer_id,
                                                         "pickup",
                                                         pickup_tw_constrain["arrive_customer_time"],
                                                         requestID,
                                                         request,
                                                         1,
                                                         vehicles_temp,
                                                         customers_temp):
                            continue

                        pickupNode = self._vehicles[vehicleID].getCurrentRoute[1]
                        delivery_tw_constrain = self._time_window_constrain(pickupNode,
                                                                            delivery_customer_id,
                                                                            "delivery",
                                                                            request)
                        if not delivery_tw_constrain["feasible"]:
                            continue
                        if not self._insertion_constrain(vehicleID,
                                                         delivery_customer_id,
                                                         "delivery",
                                                         delivery_tw_constrain["arrive_customer_time"],
                                                         requestID,
                                                         request,
                                                         2,
                                                         vehicles_temp,
                                                         customers_temp):
                            continue
                        insertion_flag = True
                        self._vehicles[vehicleID].getCurrentRoute[1].setBrotherNode(
                            self._vehicles[vehicleID].getCurrentRoute[2])
                        self._vehicles[vehicleID].getCurrentRoute[2].setBrotherNode(
                            self._vehicles[vehicleID].getCurrentRoute[1])
                        # if best_score > c11:
                        insertion_score_dict = {"score": c11,
                                                "route_pickup_index": 0,
                                                "route_delivery_index": 1,
                                                "vehicleID": vehicleID,
                                                "requestID": requestID,
                                                "pickup_customer_id": pickup_customer_id,
                                                "delivery_customer_id": delivery_customer_id,
                                                "vehicles": deepcopy(self._vehicles),
                                                "requests": deepcopy(self._requests),
                                                "customers": deepcopy(self._customers)}
                        candidate_.append(insertion_score_dict)
                        self.__sorted_candidate(candidate_)
                        # candidate_ = sorted(candidate_, key=lambda x: x["score"])
                        # if len(candidate_) > self._degree:
                        #     del candidate_[len(candidate_) - 1]
                        self._vehicles = deepcopy(vehicles_temp)
                        self._requests = deepcopy(requests_temp)
                        self._customers = deepcopy(customers_temp)
                    else:  # 在现有路线上插入需求
                        route = self._vehicles[vehicleID].getCurrentRoute
                        """
                        1、先插入pickup,再插入delivery，计算总的成本增加值
                        2、服从last in first out原则
                        """
                        route_length = len(route)
                        for i in range(1, route_length + 1):
                            # 容量约束
                            if not self._capacity_constrain(request, vehicleID, i - 1):
                                continue

                            # pickup时间窗约束
                            pickup_tw_constrain = self._time_window_constrain(route[i - 1],
                                                                              pickup_customer_id,
                                                                              "pickup",
                                                                              request)
                            if not pickup_tw_constrain["feasible"]:
                                continue

                            # 排队等待约束
                            if not self._insertion_constrain(vehicleID,
                                                             pickup_customer_id,
                                                             "pickup",
                                                             pickup_tw_constrain["arrive_customer_time"],
                                                             requestID,
                                                             request,
                                                             i,
                                                             vehicles_temp,
                                                             customers_temp):
                                continue
                            vehicles_temp1 = deepcopy(self._vehicles)
                            customers_temp1 = deepcopy(self._customers)
                            requests_temp1 = deepcopy(self._requests)
                            for j in range(i + 1, route_length + 2):
                                self._vehicles = deepcopy(vehicles_temp1)
                                self._customers = deepcopy(customers_temp1)
                                self._requests = deepcopy(requests_temp1)
                                # delivery时间窗约束
                                delivery_tw_constrain = self._time_window_constrain(route[j - 1],
                                                                                    delivery_customer_id,
                                                                                    "delivery",
                                                                                    request)
                                if not delivery_tw_constrain["feasible"]:
                                    continue

                                # last in first out 约束
                                c11 = self._LIFO_constrain(vehicleID,
                                                           route_length,
                                                           i,
                                                           j,
                                                           pickup_customer_id,
                                                           delivery_customer_id)
                                if best_score < c11:
                                    continue
                                # 排队等待约束
                                if not self._insertion_constrain(vehicleID,
                                                                 delivery_customer_id,
                                                                 "delivery",
                                                                 delivery_tw_constrain["arrive_customer_time"],
                                                                 requestID,
                                                                 request,
                                                                 j,
                                                                 vehicles_temp1,
                                                                 customers_temp1):
                                    continue

                                insertion_flag = True
                                self._vehicles[vehicleID].getCurrentRoute[i].setBrotherNode(
                                    self._vehicles[vehicleID].getCurrentRoute[j])
                                self._vehicles[vehicleID].getCurrentRoute[j].setBrotherNode(
                                    self._vehicles[vehicleID].getCurrentRoute[i])
                                insertion_score_dict = {"score": c11,
                                                        "route_pickup_index": i,
                                                        "route_delivery_index": j,
                                                        "vehicleID": vehicleID,
                                                        "requestID": requestID,
                                                        "pickup_customer_id": pickup_customer_id,
                                                        "delivery_customer_id": delivery_customer_id,
                                                        "vehicles": deepcopy(self._vehicles),
                                                        "requests": deepcopy(self._requests),
                                                        "customers": deepcopy(self._customers)}

                                candidate_.append(insertion_score_dict)
                                self.__sorted_candidate(candidate_)
                            self._vehicles = deepcopy(vehicles_temp)
                            self._requests = deepcopy(requests_temp)
                            self._customers = deepcopy(customers_temp)

                temp_score = 0
                if len(candidate_) > 1:
                    for i in range(1, self._degree):
                        temp_score += (candidate_[i]["score"] - candidate_[0]["score"])
                elif len(candidate_) == 1:  # 只能插入到一个位置
                    temp_score += np.infty
                else:
                    continue
                    # return False
                if temp_score > best_score:
                    best_score = temp_score
                    insertion_score_dict = candidate_[0]

            if insertion_flag:
                """ 选择最优结果的那一辆车"""
                unDispatchedRequestsID_set.remove(insertion_score_dict["requestID"])
                self._requests.updateDispatchedRequestPool(insertion_score_dict["requestID"], "add")
                # print(unDispatchedRequestsID_set)
                self._vehicles = insertion_score_dict["vehicles"]
                self._customers = insertion_score_dict["customers"]
                self._vehicles = insertion_score_dict["vehicles"]
            else:
                """需求分配失败"""
                print("insertion fail")
                if insertion_fail_count < unDispatchedRequestsID_num * unDispatchedRequestsID_num:
                    insertion_fail_count += 1
                    continue
                else:
                    return False
        return True

    def outputSolution(self):
        # print("operator is ", len(self._requests.getDispatchedPool))
        return self._vehicles, self._customers, self._requests


if __name__ == "__main__":
    pass
