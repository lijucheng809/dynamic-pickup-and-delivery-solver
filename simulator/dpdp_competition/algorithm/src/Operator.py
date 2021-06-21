import random
from abc import ABCMeta, abstractmethod
from typing import Dict, List
from datetime import datetime, timedelta
import numpy as np
from copy import deepcopy
import sys
from queue import PriorityQueue

from simulator.dpdp_competition.algorithm.src.vehicle import vehicle
from simulator.dpdp_competition.algorithm.src.travelCost import costDatabase
from simulator.dpdp_competition.algorithm.src.utlis import customer_request_combination, sourcePool, checks
from simulator.dpdp_competition.algorithm.src.requestPool import requestPool
from simulator.dpdp_competition.algorithm.src.customer import customer

import simulator.dpdp_competition.algorithm.src.getConfig

gConfig = simulator.dpdp_competition.algorithm.src.getConfig.get_config()


class insertOperator(metaclass=ABCMeta):

    @abstractmethod
    def insert(self):
        pass

    @abstractmethod
    def outputSolution(self):
        pass


class removeOperator(metaclass=ABCMeta):

    @abstractmethod
    def remove(self, remove_number: int):
        pass


class localSearchOperator(metaclass=ABCMeta):

    @abstractmethod
    def move(self):
        pass


class ShawRemovalOperator(removeOperator):
    def __init__(self, vehicles: Dict[str, vehicle]):
        self._vehicles = vehicles
        # 对到达时间和货量进行normalized
        min_arriveTime = np.infty
        max_arriveTime = -np.infty
        min_volume = np.infty
        max_volume = -np.infty
        startTime = datetime.strptime(gConfig["date"] + " " + gConfig["time"], "%Y-%m-%d %H:%M:%S")
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
    def _relatedness(request_1: customer_request_combination,
                     request_2: customer_request_combination):
        """
        两个request应该都是pickup点
        :param request_1:
        :param request_2:
        :return: relatedness value
        """
        assert request_1.demandType == "pickup" or request_2.demandType == "pickup"
        distance_p1_p2 = costDatabase().getTravelCost(request_1.customerID, request_2.customerID)["normal_distance"]
        distance_d1_d2 = costDatabase().getTravelCost(request_1.brotherNode.customerID,
                                                      request_2.brotherNode.customerID)["normal_distance"]
        diff_arriveTime_p1_p2 = abs(request_1.vehicleArriveTime_normal - request_2.vehicleArriveTime_normal)
        diff_arriveTime_d1_d2 = abs(request_1.brotherNode.vehicleArriveTime_normal
                                    - request_2.brotherNode.vehicleArriveTime_normal)
        diff_volume_p1_p2 = abs(request_1.volume_normal - request_2.volume_normal)

        distance_weight = gConfig["shaw_removal_distance_weight"]
        travelTime_weight = gConfig["shaw_removal_travel_time_weight"]
        demand_weight = gConfig["shaw_removal_demand_weight"]
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
                np.power(np.random.rand(), gConfig["shaw_removal_randomness_value"]) * (len(node_R_map) - 1))
            node_new = node_R_map[random_index][0]
            removals[node_new] = unSelectNodes[node_new]
            unSelectNodes.pop(node_new)
        return removals


class RandomRemovalOperator(ShawRemovalOperator):
    def __init__(self, vehicles: Dict[str, vehicle]):
        self._vehicles = vehicles

    def remove(self, remove_number: int):
        removals = dict()
        pickupNodes = self.getPickupNode()
        randomSelectNode = random.sample((list(pickupNodes.keys())), remove_number)
        for node in randomSelectNode:
            removals[node] = pickupNodes[node]
        return removals


class WorstRemovalOperator(removeOperator):
    def __init__(self, vehicles: Dict[str, vehicle], travelCost_solver=costDatabase()):
        self._initVehicles = vehicles
        self._vehicles = deepcopy(vehicles)
        self._pickupNode = dict()
        self._pickupNodeIndex = dict()  # 存储对应入参的vehicles的实际位置，因为deepcopy之后node无法作为对应原始vehicles的key值
        self._travelCost_solver = travelCost_solver
        for vehicleID in self._vehicles:
            if len(self._vehicles[vehicleID].getCurrentRoute) > 1:
                for node in self._vehicles[vehicleID].getCurrentRoute:
                    if node.demandType == "pickup":
                        self._pickupNode[node] = vehicleID
                        route_index = self._vehicles[vehicleID].getCurrentRoute.index(node)
                        self._pickupNodeIndex[node] = {"vehicle": vehicleID, "routeIndex": route_index}
                    else:
                        continue

    def _getDifferentCost(self, pickup_node: customer_request_combination):
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
        vehicle.updateTravelCost(self._travelCost_solver)
        new_cost = deepcopy(vehicle.getCurrentRouteCost)
        return old_cost - new_cost

    def _removeNodeFromRoute(self, pickup_node: customer_request_combination):
        assert pickup_node.demandType == "pickup"
        delivery_node = pickup_node.brotherNode
        self._vehicles[pickup_node.vehicleID].getCurrentRoute.remove(pickup_node)
        self._vehicles[pickup_node.vehicleID].getCurrentRoute.remove(delivery_node)
        self._vehicles[pickup_node.vehicleID].updateTravelCost(self._travelCost_solver)

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
                np.power(np.random.rand(), gConfig["worst_removal_randomness_value"]) * (len(node_cost_map) - 1))
            node_new = node_cost_map[random_index][0]
            indexes = self._pickupNodeIndex[node_new]
            node_new1 = self._initVehicles[indexes["vehicle"]].getCurrentRoute[indexes["routeIndex"]]
            removals[node_new1] = self._pickupNode[node_new]
            # removals[node_new] = self._pickupNode[node_new]
            self._removeNodeFromRoute(node_new)
            self._pickupNode.pop(node_new)
            remove_number -= 1
        return removals


class GreedyInsertionOperator(insertOperator):
    def __init__(self,
                 vehicles: Dict[str, vehicle],
                 requests: requestPool,
                 customers: Dict[str, customer],
                 travelCost_solver):
        self._source_pool = deepcopy(sourcePool(vehicles, customers, requests))
        for customerID in self._source_pool.customers:
            self._source_pool.customers[customerID].gen_node_port_map()
        self._travelCost_solver = travelCost_solver
        self._fail_insertion_requests = []

    @property
    def get_fail_insertion_requests(self):
        return self._fail_insertion_requests

    def _vehicle_customer_match(self):
        for vehicleID in self._source_pool.vehicles:
            length = len(self._source_pool.vehicles[vehicleID].getCurrentRoute)
            if length > 1:
                for index, node in enumerate(self._source_pool.vehicles[vehicleID].getCurrentRoute):
                    if node.requestID != 0 :
                        customer_object = self._source_pool.customers[node.customerID]
                        customer_object.getDispatchedRequestSet[node.requestID] = node
                        if node.requestID in customer_object.get_node_port_map:
                            port_index = customer_object.get_node_port_map[node.requestID]
                            customer_object.getCurrentPortStatus[port_index[0]][port_index[1]] = node

    def _getResource(self):
        minpq_unDispatched_request = PriorityQueue()
        available_vehicleID_set = []
        for requestID in self._source_pool.requests.getUnDispatchedPool:
            creation_time = self._source_pool.requests.getUnDispatchedPool[requestID]["creation_time"]
            minpq_unDispatched_request.put((creation_time, requestID))
        for vehicleID in self._source_pool.vehicles:
            if self._source_pool.vehicles[vehicleID].getStatus == "busy" or self._source_pool.vehicles[vehicleID].getStatus == "idle":
                available_vehicleID_set.append(vehicleID)
            else:
                continue

        # random.shuffle(available_vehicleID_set)
        return available_vehicleID_set, minpq_unDispatched_request

    def _time_window_constrain(self,
                               pre_node: customer_request_combination,
                               target_customer_id: str,
                               demand_type: str,
                               request: dict):

        demand_info = demand_type + "_demand_info"
        if datetime.strptime(request[demand_info]["time_window"][1], "%Y-%m-%d %H:%M:%S") < datetime.strptime(
                request[demand_info]["time_window"][0], "%Y-%m-%d %H:%M:%S"):
            latest_leave_time = datetime.strptime(request[demand_info]["time_window"][1], "%Y-%m-%d %H:%M:%S") \
                                + timedelta(days=1)
        else:
            latest_leave_time = datetime.strptime(request[demand_info]["time_window"][1], "%Y-%m-%d %H:%M:%S")
        order_creation_time = datetime.strptime(request[demand_info]["time_window"][0], "%Y-%m-%d %H:%M:%S")
        travel_cost = self._travelCost_solver.getTravelCost(pre_node.customerID, target_customer_id)
        arrive_customer_time = pre_node.vehicleDepartureTime + timedelta(seconds=travel_cost["travel_time"])
        leave_customer_time = arrive_customer_time + timedelta(seconds=request[demand_info]["process_time"])
        if pre_node.customerID != target_customer_id:
            leave_customer_time += timedelta(seconds=gConfig["static_process_time_on_customer"])
        flag = True
        if arrive_customer_time < order_creation_time:
            flag = False
        if leave_customer_time > latest_leave_time:
            flag = False
        return {"feasible": flag, "arrive_customer_time": arrive_customer_time, "travel_cost": travel_cost}

    def _capacity_constrain(self, request, vehicleID, route_index):
        route_length = len(self._source_pool.vehicles[vehicleID].getCurrentRoute)
        request_volume = request["pickup_demand_info"]["volume"]
        vehicle_capacity = self._source_pool.vehicles[vehicleID].getCapacity
        for i in range(route_index, route_length):
            if request_volume + self._source_pool.vehicles[vehicleID].getCurrentVolume(i+1) > vehicle_capacity:
                return False
        return True

    def _insertion_constrain(self,
                             vehicleID,
                             customerID,
                             demand_type,
                             arrive_time,
                             requestID,
                             request,
                             route_index,
                             source_pool_temp):
        if not self._source_pool.vehicles[vehicleID].feasibleInsertion(self._source_pool.customers,
                                                                       customerID,
                                                                       demand_type,
                                                                       arrive_time,
                                                                       requestID,
                                                                       request,
                                                                       route_index):
            self._source_pool = deepcopy(source_pool_temp)
            self._vehicle_customer_match()
            return False
        else:
            return True

    def _LIFO_constrain(self,
                        vehicleID,
                        route_length,
                        pickup_route_index,
                        delivery_route_index,
                        pickup_customer_id,
                        delivery_customer_id):
        route = self._source_pool.vehicles[vehicleID].getCurrentRoute
        min_insert_index = np.infty
        for k in range(1, pickup_route_index):
            if route[k].demandType == "pickup":
                min_insert_index = min(min_insert_index, route.index(route[k].brotherNode))
        if delivery_route_index > min_insert_index and pickup_route_index != len(route)-1:
            return np.infty

        max_insert_index = -np.infty
        min_delivery_only_insert = np.infty
        for k in range(pickup_route_index + 1, len(route)):
            if route[k].demandType == "pickup":
                max_insert_index = max(max_insert_index, route.index(route[k].brotherNode))
            elif not route[k].brotherNode and route[k].demandType == "delivery":
                min_delivery_only_insert = min(min_delivery_only_insert, k)
        if delivery_route_index > min_delivery_only_insert:
            return np.infty
        if delivery_route_index <= max_insert_index:
            return np.infty
        if max_insert_index == -np.infty and min_insert_index == np.infty and delivery_route_index != pickup_route_index + 1:
            return np.infty

        travel_const1 = self._travelCost_solver.getTravelCost(route[pickup_route_index - 1].customerID,
                                                              pickup_customer_id)
        if pickup_route_index == route_length:
            travel_const2 = self._travelCost_solver.getTravelCost(pickup_customer_id,
                                                                  delivery_customer_id)
            c11 = travel_const1["distance"] + travel_const2["distance"]
        elif pickup_route_index < route_length and delivery_route_index == route_length + 1:
            travel_const2 = self._travelCost_solver.getTravelCost(pickup_customer_id,
                                                                  route[pickup_route_index + 1].customerID)
            travel_const3 = self._travelCost_solver.getTravelCost(route[pickup_route_index - 1].customerID,
                                                                  route[pickup_route_index + 1].customerID)
            travel_const4 = self._travelCost_solver.getTravelCost(route[delivery_route_index - 1].customerID,
                                                                  delivery_customer_id)
            c11 = travel_const1["distance"] + travel_const2["distance"] \
                  - travel_const3["distance"] + travel_const4["distance"]
        else:
            travel_const2 = self._travelCost_solver.getTravelCost(pickup_customer_id,
                                                                  route[pickup_route_index + 1].customerID)
            travel_const3 = self._travelCost_solver.getTravelCost(route[pickup_route_index - 1].customerID,
                                                                  route[pickup_route_index + 1].customerID)
            travel_const4 = self._travelCost_solver.getTravelCost(route[delivery_route_index - 1].customerID,
                                                                  delivery_customer_id)
            travel_const5 = self._travelCost_solver.getTravelCost(delivery_customer_id,
                                                                  route[delivery_route_index].customerID)
            travel_const6 = self._travelCost_solver.getTravelCost(route[delivery_route_index - 1].customerID,
                                                                  route[delivery_route_index].customerID)

            c11 = travel_const1["distance"] + travel_const2["distance"] \
                  - travel_const3["distance"] + travel_const4["distance"] \
                  + travel_const5["distance"] - travel_const6["distance"]
        return c11

    def _orderMatched(self, vehicleID, request):
        route = self._source_pool.vehicles[vehicleID].getCurrentRoute
        pickup_customer_id = request["pickup_demand_info"]["customer_id"]
        delivery_customer_id = request["delivery_demand_info"]["customer_id"]
        requestID = request["requestID"]
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
                if self._capacity_constrain(request, vehicleID, index) \
                        and self._time_window_constrain(node, pickup_customer_id, "pickup", request)["feasible"]:
                    pickup_flag = True
                    pickup_route_index = index + 1
            if node.customerID == delivery_customer_id and not delivery_flag and pickup_flag:
                # delivery_flag = True
                delivery_route_index = index + 1
        return {"pickup_flag": pickup_flag,
                "delivery_flag": delivery_flag,
                "pickup_route_index": pickup_route_index,
                "delivery_route_index": delivery_route_index}

    def _PD_insertion(self,
                      vehicleID,
                      request,
                      pickup_customer_id,
                      delivery_customer_id,
                      requestID,
                      source_pool_temp,
                      best_score):
        """
        1、先插入pickup,再插入delivery，计算总的成本增加值
        2、服从last in first out原则
        """
        route_length = len(self._source_pool.vehicles[vehicleID].getCurrentRoute)
        insertion_score_dict = {}
        for i in range(1, route_length + 1):
            route = self._source_pool.vehicles[vehicleID].getCurrentRoute
            if i == 1 and route[i].demandType == "delivery":
                continue
            requestID_new = request["requestID"]
            if "-" in requestID_new:
                _index = requestID_new.index("-")
                requestID_new = requestID_new[:_index]
            if 1 < i < route_length-1 and requestID_new in route[i-1].requestID and requestID_new in route[i+1].requestID:
                continue
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
                                             source_pool_temp):
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

    def _delivery_insertion(self,
                            pickup_route_index,
                            route_length,
                            pickup_customer_id,
                            delivery_customer_id,
                            request,
                            requestID,
                            vehicleID,
                            source_pool_temp,
                            best_score):
        source_pool_temp1 = deepcopy(self._source_pool)
        insertion_score_dict = {}
        for j in range(pickup_route_index + 1, route_length + 2):
            self._source_pool = deepcopy(source_pool_temp1)
            self._vehicle_customer_match()
            route = self._source_pool.vehicles[vehicleID].getCurrentRoute
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
                                       pickup_route_index,
                                       j,
                                       pickup_customer_id,
                                       delivery_customer_id)
            c11 += self._get_current_mileage(source_pool_temp.vehicles)
            if best_score < c11 or c11 == np.infty:
                continue

            # 排队等待约束
            if not self._insertion_constrain(vehicleID,
                                             delivery_customer_id,
                                             "delivery",
                                             delivery_tw_constrain["arrive_customer_time"],
                                             requestID,
                                             request,
                                             j,
                                             source_pool_temp1):
                continue

            self._source_pool.vehicles[vehicleID].getCurrentRoute[pickup_route_index].setBrotherNode(
                self._source_pool.vehicles[vehicleID].getCurrentRoute[j])
            self._source_pool.vehicles[vehicleID].getCurrentRoute[j].setBrotherNode(
                self._source_pool.vehicles[vehicleID].getCurrentRoute[pickup_route_index])
            # if best_score > c11:
            best_score = c11
            insertion_score_dict = {"score": best_score,
                                    "vehicleID": vehicleID,
                                    "requestID": requestID,
                                    "sourcePool": deepcopy(self._source_pool)}
            if j < route_length + 1 and delivery_customer_id == route[j - 1].customerID:
                """这里的逻辑是，找到同批次装卸货的点，一定是cost最小的，所以没必要继续搜寻"""
                break
        self._source_pool = deepcopy(source_pool_temp)
        self._vehicle_customer_match()
        return insertion_score_dict

    def insert(self,
               time2Go=datetime.strptime(gConfig["date"] + " 0:0:0", "%Y-%m-%d %H:%M:%S"),
               tp="constructor") -> bool:
        self._vehicle_customer_match()
        available_vehicleID_set, minpq_unDispatched_request = self._getResource()
        # print(unDispatchedRequestsID_set)
        while not minpq_unDispatched_request.empty():
            # insertion_flag = False  # 判断是否插入成功
            # insertion_score_dict = dict()
            # best_score = np.infty
            requestID = minpq_unDispatched_request.get()[1]
            request = self._source_pool.requests.getUnDispatchedPool[requestID]
            print("当前requestID:", requestID, "creation_time:", request["creation_time"])
            # print("当前需要决定的requestID:", requestID)
            source_pool_temp = deepcopy(self._source_pool)
            # random.shuffle(available_vehicleID_set)
            insertion_flag = False  # 判断是否插入成功
            insertion_score_dict = dict()
            best_score = np.infty
            for vehicleID in available_vehicleID_set:
                pickup_customer_id = request["pickup_demand_info"]["customer_id"]
                delivery_customer_id = request["delivery_demand_info"]["customer_id"]
                if request["pickup_demand_info"]["volume"] > self._source_pool.vehicles[vehicleID].getCapacity:
                    """需求拆分"""
                    print("需求超过最大载重！！  ", requestID)
                    continue
                if len(self._source_pool.vehicles[vehicleID].getCurrentRoute) == 1:  # 安排一辆空闲的车
                    """车辆从起始点出发"""
                    depotNode = self._source_pool.vehicles[vehicleID].getCurrentRoute[0]
                    if depotNode.requestID == 0 and not depotNode.vehicleArriveTime:
                        self._source_pool.vehicles[vehicleID].getCurrentRoute[0].setVehicleArriveTime(time2Go)
                        self._source_pool.vehicles[vehicleID].getCurrentRoute[0].setVehicleDepartureTime(time2Go)
                    depotID = self._source_pool.vehicles[vehicleID].getDepotID
                    travel_cost_depot2pickup = self._travelCost_solver.getTravelCost(depotID, pickup_customer_id)
                    travel_cost_pickup2delivery = self._travelCost_solver.getTravelCost(pickup_customer_id,
                                                                                        delivery_customer_id)
                    pickup_tw_constrain = self._time_window_constrain(depotNode,
                                                                      pickup_customer_id,
                                                                      "pickup",
                                                                      request)
                    if not pickup_tw_constrain["feasible"]:
                        continue

                    c11 = travel_cost_depot2pickup["distance"] + travel_cost_pickup2delivery["distance"]
                    c11 += self._get_current_mileage(source_pool_temp.vehicles)
                    if best_score < c11:
                        continue
                    if not self._insertion_constrain(vehicleID,
                                                     pickup_customer_id,
                                                     "pickup",
                                                     pickup_tw_constrain["arrive_customer_time"],
                                                     requestID,
                                                     request,
                                                     1,
                                                     source_pool_temp):
                        continue

                    pickupNode = self._source_pool.vehicles[vehicleID].getCurrentRoute[1]
                    delivery_tw_constrain = self._time_window_constrain(pickupNode,
                                                                        delivery_customer_id,
                                                                        "delivery",
                                                                        request)
                    if not delivery_tw_constrain["feasible"]:
                        self._source_pool = deepcopy(source_pool_temp)
                        self._vehicle_customer_match()
                        continue
                    if not self._insertion_constrain(vehicleID,
                                                     delivery_customer_id,
                                                     "delivery",
                                                     delivery_tw_constrain["arrive_customer_time"],
                                                     requestID,
                                                     request,
                                                     2,
                                                     source_pool_temp):
                        continue
                    insertion_flag = True
                    self._source_pool.vehicles[vehicleID].getCurrentRoute[1].setBrotherNode(
                        self._source_pool.vehicles[vehicleID].getCurrentRoute[2])
                    self._source_pool.vehicles[vehicleID].getCurrentRoute[2].setBrotherNode(
                        self._source_pool.vehicles[vehicleID].getCurrentRoute[1])
                    best_score = c11
                    insertion_score_dict = {"score": best_score,
                                            "vehicleID": vehicleID,
                                            "requestID": requestID,
                                            "sourcePool": deepcopy(self._source_pool)}
                    self._source_pool = deepcopy(source_pool_temp)
                    self._vehicle_customer_match()
                else:  # 在现有路线上插入需求
                    pd_insert_info = self._orderMatched(vehicleID, request)
                    route_length = len(self._source_pool.vehicles[vehicleID].getCurrentRoute)
                    flag_temp = False
                    if pd_insert_info["pickup_flag"]:
                        same_node = self._source_pool.vehicles[vehicleID].getCurrentRoute[
                            pd_insert_info["pickup_route_index"] - 1]
                        if self._insertion_constrain(vehicleID,
                                                     pickup_customer_id,
                                                     "pickup",
                                                     same_node.vehicleArriveTime,
                                                     requestID,
                                                     request,
                                                     pd_insert_info["pickup_route_index"],
                                                     source_pool_temp):
                            flag_temp = True
                            if pd_insert_info["delivery_flag"]:
                                same_node = self._source_pool.vehicles[vehicleID].getCurrentRoute[
                                    pd_insert_info["delivery_route_index"]]
                                if self._insertion_constrain(vehicleID,
                                                             delivery_customer_id,
                                                             "delivery",
                                                             same_node.vehicleArriveTime,
                                                             requestID,
                                                             request,
                                                             pd_insert_info["delivery_route_index"] ,
                                                             source_pool_temp):
                                    best_score = 0
                                    insertion_flag = True
                                    p_index = pd_insert_info["pickup_route_index"]
                                    d_index = pd_insert_info["delivery_route_index"] + 1
                                    self._source_pool.vehicles[vehicleID].getCurrentRoute[p_index].setBrotherNode(
                                        self._source_pool.vehicles[vehicleID].getCurrentRoute[d_index])
                                    self._source_pool.vehicles[vehicleID].getCurrentRoute[d_index].setBrotherNode(
                                        self._source_pool.vehicles[vehicleID].getCurrentRoute[p_index])
                                    insertion_score_dict = {"score": best_score,
                                                            "vehicleID": vehicleID,
                                                            "requestID": requestID,
                                                            "sourcePool": deepcopy(self._source_pool)}
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
                    if not flag_temp:
                        insertion_score_dict_temp = self._PD_insertion(
                                                                        vehicleID,
                                                                        request,
                                                                        pickup_customer_id,
                                                                        delivery_customer_id,
                                                                        requestID,
                                                                        source_pool_temp,
                                                                        best_score)
                        if insertion_score_dict_temp:
                            insertion_flag = True
                            insertion_score_dict = insertion_score_dict_temp
                            best_score = insertion_score_dict["score"]

            if insertion_flag:
                """ 选择最优结果的那一辆车"""
                # unDispatchedRequestsID_set.remove(insertion_score_dict["requestID"])
                # print(unDispatchedRequestsID_set)
                self._source_pool = insertion_score_dict["sourcePool"]
                self._source_pool.requests.updateDispatchedRequestPool(insertion_score_dict["requestID"], "add")
                self._vehicle_customer_match()
                # checks().print_solution(self._source_pool.vehicles)
                # print("------------------------------------------------------------------------")

            else:
                """需求分配失败"""
                print("insertion fail requestID:", requestID,
                      "creation_time:", request["creation_time"], file=sys.stderr)
                self._fail_insertion_requests.append({requestID:
                                                          self._source_pool.requests.getUnDispatchedPool[requestID]})
                # unDispatchedRequestsID_set.remove(requestID)
                source_pool_temp.requests.getUnDispatchedPool.pop(requestID)
                self._source_pool = deepcopy(source_pool_temp)
                self._vehicle_customer_match()
        if self._fail_insertion_requests:
            # print(self._fail_insertion_requests)
            return False
        return True

    def _get_current_mileage(self, vehicles):
        score = 0
        for vehicleID in vehicles:
            vehicles[vehicleID].updateTravelCost(self._travelCost_solver)
            score += vehicles[vehicleID].getCurrentRouteCost
            score += vehicles[vehicleID].getMileage
        return score

    @property
    def getObjectiveScore(self):
        score = 0
        for vehicleID in self._source_pool.vehicles:
            self._source_pool.vehicles[vehicleID].updateTravelCost(self._travelCost_solver)
            score += self._source_pool.vehicles[vehicleID].getCurrentRouteCost
            score += self._source_pool.vehicles[vehicleID].getMileage
        return score

    def outputSolution(self):
        return self._source_pool.vehicles, self._source_pool.customers, self._source_pool.requests


class RegretInsertionOperator(GreedyInsertionOperator):
    def __init__(self,
                 vehicles: Dict[str, vehicle],
                 requests: requestPool,
                 customers: Dict[str, customer],
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
               time2Go=datetime.strptime(gConfig["date"] + " 0:0:0", "%Y-%m-%d %H:%M:%S"),
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
