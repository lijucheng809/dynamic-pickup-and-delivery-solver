import json
import sys
from typing import Dict
from datetime import datetime, timedelta
import time
import os

from simulator.dpdp_competition.algorithm.src.common.customer import Customer
from simulator.dpdp_competition.algorithm.src.utils.utlis import feasibleRearrangePortAssignmentSchedule
from simulator.dpdp_competition.algorithm.src.common.customer_request_combination import CustomerRequestCombination
from simulator.dpdp_competition.algorithm.conf.configs import Configs
from simulator.dpdp_competition.algorithm.src.enum.constrain_enum import ConstrainEnum
from simulator.dpdp_competition.algorithm.src.utils.route_cost_util import route_cost
from simulator.dpdp_competition.algorithm.src.enum.demand_type_enum import DemandTypeEnum
from simulator.dpdp_competition.algorithm.src.enum.request_info_enum import RequestInfoEnum
from simulator.dpdp_competition.algorithm.src.enum.item_info_enum import ItemInfoEnum
from simulator.dpdp_competition.algorithm.src.enum.route_cost_enum import RouteCostEnum
from simulator.dpdp_competition.algorithm.src.enum.demand_info_enum import DemandInfoEnum


class Vehicle(object):
    def __init__(self, vehicle_id, capacity, position, gps_id, current_volume=0, status='off_duty', mileage=0,
                 dimension=None, type="A"):
        """
        :param vehicle_id:
        :param capacity:
        :param position:
        :param route:
            [{"customer", request, "time_window", "arrive_time", "waiting_timespan", "processingTimespan", "departure_time"}, {}, ...]
        :param current_volume:
        :param status: "idle, en_route, serving, off_duty"
        """
        self._vehicleID = vehicle_id
        self._capacity = capacity
        self._route = []
        self._depotID = gps_id
        self._currentVolume = current_volume
        self._status = status
        self._position = position
        self._finishServedCustomerList = []
        self._staticServeTimeOnCustomer = Configs.static_process_time_on_customer
        self._currentTravelCost = 0
        self._update_time = None
        self._mileage = mileage
        self._dimension = dimension  # 箱规尺寸
        self._type = type
        self._compatible_item_type_list = None  # 与车辆兼容的货物类型列表
        self._delivery_only_id_bin_map = {}
        self._incompatible_item_type_set = set()  # 车上装在的货物中互斥的货物类型集合， 仅存放delivery_only的货物

    @property
    def get_incompatible_item_type_set(self):
        return self._incompatible_item_type_set

    @property
    def get_delivery_only_id_bin_map(self):
        return self._delivery_only_id_bin_map

    @property
    def get_compatible_item_type_list(self):
        return self._compatible_item_type_list

    @property
    def getMileage(self):
        return self._mileage

    @property
    def getUpdateTime(self):
        return self._update_time

    @property
    def getVehicleID(self):
        return self._vehicleID

    @property
    def getCurrentRoute(self):
        return self._route

    @property
    def getStatus(self):
        return self._status

    @property
    def getCurrentPosition(self):
        return self._position

    @property
    def getCapacity(self):
        return self._capacity

    @property
    def getDepotID(self):
        return self._depotID

    @property
    def getCurrentRouteCost(self):
        return self._currentTravelCost

    @property
    def get_vehicle_dimension(self):
        return self._dimension

    def set_compatible_items(self, compatible_item_type_list: list):
        self._compatible_item_type_list = compatible_item_type_list

    def set_vehicle_dimension(self, vehicle_dimension):
        self._dimension = vehicle_dimension

    def set_update_time(self, Time):
        self._update_time = Time

    def updateTravelCost(self):
        if len(self._route) > 1:
            total_distance = 0
            total_travel_time = 0
            for index in range(len(self._route) - 1):
                node1, node2 = self._route[index], self._route[index + 1]
                travel_cost = route_cost.getTravelCost(node1.customerID, node2.customerID)
                total_distance += travel_cost[RouteCostEnum.distance.name]
                total_travel_time += travel_cost[RouteCostEnum.travel_time.name]
            weight = Configs.weighted_objective_function
            self._currentTravelCost = weight * total_distance + (1 - weight) * total_travel_time
        else:
            self._currentTravelCost = 0

    def getCurrentVolume(self, route_index):
        current_volume = 0
        for i in range(route_index):
            current_volume += self._route[i].volume
        return current_volume

    def underCapacity(self):
        volume = 0
        if len(self._route) > 1:
            for i in range(len(self._route)):
                volume += self._route[i].volume
                if volume > self._capacity:
                    return False
        return True

    def setPDNodeConnection(self, pickup_route_index: int, delivery_route_index: int):
        """
        用于后续领域搜索，快速找到PD在路径中的位置
        :param pickup_route_index:
        :param delivery_route_index:
        :return:
        """
        self._route[pickup_route_index].setBrotherNodeRouteIndex(delivery_route_index)
        self._route[delivery_route_index].setBrotherNodeRouteIndex(pickup_route_index)

    def deleteNodeFromRoute(self, pickup_node_index):
        # 应该成对删除， 即同时将Pickup以及delivery删除
        pickup_node = self._route[pickup_node_index]
        delivery_node = pickup_node.brotherNode
        self._route.remove(pickup_node)
        self._route.remove(delivery_node)
        # 重新安排node的左右孩子
        if len(self._route) > 1:
            self._route[0].setRightNode(self._route[1])
            for i in range(1, len(self._route) - 1):
                self._route[i].setRightNode(self._route[i + 1])
                self._route[i].setLeftNode(self._route[i - 1])
            self._route[len(self._route) - 1].setLeftNode(self._route[len(self._route) - 2])
            self._route[len(self._route) - 1].setRightNode(None)
        else:
            self._route[0].setRightNode(None)

    def addNode2Route(self, node: CustomerRequestCombination, index: int):
        self._route.insert(index, node)

    def deleteFinishServeNodeFromRoute(self):
        self._route[1].setLeftNode = None
        self.updateVolume(-self._route[0].volume)
        del self._route[0]

    def updateVolume(self, volume):
        self._currentVolume += volume

    def updatePosition(self, position):
        self._position = position

    def updateStatus(self, status):
        self._status = status

    def feasibleInsertion(self,
                          customers: Dict[str, Customer],
                          customer_id: str,
                          demand_type: str,
                          vehicle_arrive_time: datetime,
                          request: dict,
                          node_index_in_route: int) -> bool:
        """
        可能需要递归，因为每次新插入需求会影响很多站点的卡位分配情况
        :return: bool
        """
        brother_customer_id = request[demand_type + "_demand_info"][DemandInfoEnum.brother_customer.name]
        node = CustomerRequestCombination(customer_id,
                                          request[RequestInfoEnum.requestID.name],
                                          demand_type,
                                          brother_customer_id,
                                          request[demand_type + "_demand_info"][DemandInfoEnum.volume.name],
                                          request[demand_type + "_demand_info"][DemandInfoEnum.time_window.name],
                                          request[demand_type + "_demand_info"][DemandInfoEnum.process_time.name],
                                          self._vehicleID)
        node.setVehicleArriveTime(vehicle_arrive_time)
        self.addNode2Route(node, node_index_in_route)
        if node_index_in_route > 0:
            self._route[node_index_in_route].setLeftNode(self._route[node_index_in_route - 1])
            self._route[node_index_in_route - 1].setRightNode(self._route[node_index_in_route])
        if node_index_in_route < len(self._route) - 1:
            self._route[node_index_in_route].setRightNode(self._route[node_index_in_route + 1])
            self._route[node_index_in_route + 1].setLeftNode(self._route[node_index_in_route])
        if request[RequestInfoEnum.requestID.name] not in customers[customer_id].getUnfinishedDemands:
            customers[customer_id].addNewDemand(request[RequestInfoEnum.requestID.name], request[demand_type + "_demand_info"])
        self.updateVolume(request[demand_type + "_demand_info"][DemandInfoEnum.volume.name])

        if demand_type == DemandTypeEnum.delivery.name and not self.underCapacity():  # 因为PD问题的特殊性，需要在delivery插入后，对载重约束再做一次判断
            return False

        if node.requestID not in customers[node.customerID].getDispatchedRequestSet:
            customers[node.customerID].getDispatchedRequestSet[node.requestID] = node
        assert not customers[node.customerID].getDispatchedRequestSet[node.requestID].brotherNode
        if Configs.constrains[ConstrainEnum.port_resource]:
            flag = feasibleRearrangePortAssignmentSchedule(customers, customer_id, node)
            if flag:
                vehicle_node = self._route[node_index_in_route]
                vehicle_left_node = vehicle_node.leftNode
                customer_left_node = customers[vehicle_node.customerID].getDispatchedRequestSet[
                    vehicle_node.requestID].leftNode
                assert vehicle_left_node == customer_left_node
                if vehicle_left_node != customer_left_node:
                    return False
                return True
            else:
                return False
        else:
            # todo 更新后续节点的到达和离开时间
            leave_time = vehicle_arrive_time + timedelta(seconds=Configs.static_process_time_on_customer +
                                                                 node.processTime)
            node.setVehicleDepartureTime(leave_time)
            if node_index_in_route < len(self._route) - 1:
                duration = route_cost.getTravelCost(node.customerID,
                                                    self._route[node_index_in_route + 1].customerID)[RouteCostEnum.travel_time.name]
                new_arrive_time = leave_time+timedelta(seconds=duration)
                is_advance_arrive = True
                if new_arrive_time > self._route[node_index_in_route+1].vehicleArriveTime:
                    time_delta = (new_arrive_time-self._route[node_index_in_route+1].vehicleArriveTime).seconds
                else:
                    is_advance_arrive = False
                    time_delta = (self._route[node_index_in_route+1].vehicleArriveTime - new_arrive_time).seconds
                for i in range(node_index_in_route+1, len(self._route)):
                    if is_advance_arrive:
                        self._route[i].vehicleArriveTime = self._route[i].vehicleArriveTime - timedelta(seconds=time_delta)
                        self._route[i].vehicleDepartureTime = self._route[i].vehicleArriveTime - timedelta(
                            seconds=time_delta)
                    else:
                        if self._route[i].vehicleDepartureTime + timedelta(seconds=time_delta) \
                                > datetime.strptime(self._route[i].timeWindow[1], "%Y-%m-%d %H:%M:%S"):
                            return False
                        else:
                            self._route[i].vehicleArriveTime = self._route[i].vehicleArriveTime + timedelta(
                                seconds=time_delta)
                            self._route[i].vehicleDepartureTime = self._route[i].vehicleArriveTime + timedelta(
                                seconds=time_delta)
                return True

            else:
                return True

    def resetDepot(self, destination_info, customers):
        """
        如果当前车辆为有任务状态（有目的地点，且目的地点必须要执行），则需要将目的地作为整个路径的起始点来做规划
        :return:
        """
        self._status = "busy"
        depot_node = CustomerRequestCombination(destination_info.customerID,
                                                destination_info.requestID,
                                                "depot",
                                                None,
                                                destination_info.volume,
                                                destination_info.timeWindow,
                                                destination_info.processTime,
                                                self._vehicleID)
        depot_node.setVehicleArriveTime(destination_info.arriveTime)
        customers[depot_node.customerID].getDispatchedRequestSet[depot_node.requestID] = depot_node
        if Configs.constrains[ConstrainEnum.port_resource]:
            feasibleRearrangePortAssignmentSchedule(customers, destination_info.customerID, depot_node)
        self._route.append(depot_node)

    def gen_fix_route(self,
                      customers,
                      request_id_on_order,
                      ongoing_items_map,
                      requests_items_map):
        time_out_requests = {}
        if os.path.exists(Configs.time_out_requests):
            with open(Configs.time_out_requests, "r") as f:
                time_out_requests = json.load(f)
        while request_id_on_order:
            requestID = request_id_on_order.pop()
            customerID = ongoing_items_map[requests_items_map[requestID][DemandTypeEnum.delivery_only.name][0]][ItemInfoEnum.delivery_factory_id.name]
            volume, process_time = 0, 0
            time_window_left, time_window_right = None, None
            bins = []
            for item_id in requests_items_map[requestID][DemandTypeEnum.delivery_only.name]:
                if Configs.constrains[ConstrainEnum.bin_packing]:
                    bins.append(ongoing_items_map[item_id][ItemInfoEnum.dimension.name])
                if Configs.constrains[ConstrainEnum.incompatible_items]:
                    self._incompatible_item_type_set = self._incompatible_item_type_set.union(
                        set(ongoing_items_map[item_id][RequestInfoEnum.incompatible_item_type_list.name]))
                volume -= ongoing_items_map[item_id][ItemInfoEnum.demand.name]
                process_time += ongoing_items_map[item_id][ItemInfoEnum.unload_time.name]
                creation_time = ongoing_items_map[item_id][ItemInfoEnum.creation_time.name]
                committed_completion_time = ongoing_items_map[item_id][ItemInfoEnum.committed_completion_time.name]
                creation_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(creation_time))
                committed_completion_time = time.strftime("%Y-%m-%d %H:%M:%S",
                                                          time.localtime(committed_completion_time))
                creation_time = datetime.strptime(creation_time, "%Y-%m-%d %H:%M:%S")
                committed_completion_time = datetime.strptime(committed_completion_time, "%Y-%m-%d %H:%M:%S")
                if not time_window_left and not time_window_right:
                    time_window_left = creation_time
                    time_window_right = committed_completion_time
                    requestID_temp = requestID[:requestID.index("V")]
                    if requestID_temp in time_out_requests:
                        time_window_right = time_out_requests[requestID_temp][RequestInfoEnum.pickup_demand_info.name][DemandInfoEnum.time_window.name][1]
                else:
                    time_window_left = max(creation_time, time_window_left)
                    time_window_right = min(committed_completion_time, time_window_right)
            self._delivery_only_id_bin_map[requestID] = bins
            node = CustomerRequestCombination(customerID,
                                              requestID,
                                              DemandTypeEnum.delivery_only.name,
                                              None,
                                              volume,
                                              [str(time_window_left), str(time_window_right)],
                                              process_time,
                                              self._vehicleID)
            left_node = self._route[len(self._route) - 1]
            travel_cost = route_cost.getTravelCost(left_node.customerID, customerID)
            arrive_time = left_node.vehicleDepartureTime + timedelta(seconds=travel_cost[RouteCostEnum.travel_time.name])
            node.setVehicleArriveTime(arrive_time)
            left_node.setRightNode(node)
            node.setLeftNode(left_node)
            self._route.append(node)
            self.updateVolume(volume)
            if node.requestID not in customers[node.customerID].getDispatchedRequestSet:
                customers[node.customerID].getDispatchedRequestSet[node.requestID] = node
            # todo 装卸货资源约束，后续设置开关
            if Configs.constrains[ConstrainEnum.port_resource]:
                flag = feasibleRearrangePortAssignmentSchedule(customers, customerID, node, tp="gen_fixed_route")
                if not flag:
                    print("固定路线生成失败, requestID:", node.requestID, file=sys.stderr)
            else:
                leave_time = arrive_time + timedelta(seconds=Configs.static_process_time_on_customer + node.processTime)
                node.setVehicleDepartureTime(leave_time)

    def force_insertion(self, request, customers):
        pickup_customer_id = request[RequestInfoEnum.pickup_demand_info.name][DemandInfoEnum.customer_id.name]
        delivery_customer_id = request[RequestInfoEnum.delivery_demand_info.name][DemandInfoEnum.customer_id.name]
        requestID = request[RequestInfoEnum.requestID.name]
        process_time = request[RequestInfoEnum.pickup_demand_info.name][DemandInfoEnum.process_time.name]
        volume = request[RequestInfoEnum.pickup_demand_info.name][DemandInfoEnum.volume.name]
        time_window_left = request[RequestInfoEnum.pickup_demand_info.name][DemandInfoEnum.time_window.name][0]
        time_window_right = request[RequestInfoEnum.pickup_demand_info.name][DemandInfoEnum.time_window.name][1]
        pickup_node = CustomerRequestCombination(pickup_customer_id,
                                                 requestID,
                                                 DemandTypeEnum.pickup.name,
                                                 None,
                                                 volume,
                                                 [time_window_left, time_window_right],
                                                 process_time,
                                                 self._vehicleID)
        left_node = self._route[len(self._route) - 1]
        travel_cost = route_cost.getTravelCost(left_node.customerID, pickup_customer_id)
        arrive_time = left_node.vehicleDepartureTime + timedelta(seconds=travel_cost[RouteCostEnum.travel_time.name])
        pickup_node.setVehicleArriveTime(arrive_time)
        departure_time = arrive_time + timedelta(seconds=Configs.static_process_time_on_customer + process_time)
        pickup_node.setVehicleDepartureTime(departure_time)
        left_node.setRightNode(pickup_node)
        pickup_node.setLeftNode(left_node)
        self._route.append(pickup_node)
        delivery_node = CustomerRequestCombination(delivery_customer_id,
                                                   requestID,
                                                   DemandTypeEnum.delivery.name,
                                                   None,
                                                   -volume,
                                                   [time_window_left, time_window_right],
                                                   process_time,
                                                   self._vehicleID)
        left_node = self._route[len(self._route) - 1]
        travel_cost = route_cost.getTravelCost(left_node.customerID, delivery_customer_id)
        arrive_time = left_node.vehicleDepartureTime + timedelta(seconds=travel_cost[RouteCostEnum.travel_time.name])
        delivery_node.setVehicleArriveTime(arrive_time)
        departure_time = arrive_time + timedelta(seconds=Configs.static_process_time_on_customer + process_time)
        delivery_node.setVehicleDepartureTime(departure_time)
        left_node.setRightNode(delivery_node)
        delivery_node.setLeftNode(left_node)
        pickup_node.setBrotherNode(delivery_node)
        delivery_node.setBrotherNode(pickup_node)
        if pickup_node.requestID not in customers[pickup_node.customerID].getDispatchedRequestSet:
            customers[pickup_node.customerID].getDispatchedRequestSet[pickup_node.requestID] = pickup_node
        if delivery_node.requestID not in customers[delivery_node.customerID].getDispatchedRequestSet:
            customers[delivery_node.customerID].getDispatchedRequestSet[delivery_node.requestID] = delivery_node
        self._route.append(delivery_node)

    def activateVehicle(self, volume=0):
        self._status = 'idle'
        depot_node = CustomerRequestCombination(self._depotID,
                                                0,
                                                "depot",
                                                None,
                                                volume,
                                                None,
                                                0,
                                                self._vehicleID)
        self._route.append(depot_node)


if __name__ == "__main__":
    test = [[] for i in range(5)]
    print(test)
