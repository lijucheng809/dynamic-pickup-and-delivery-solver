from typing import List, Dict
from datetime import datetime, timedelta
import time

from simulator.dpdp_competition.algorithm.vrppd.customer import customer
from simulator.dpdp_competition.algorithm.vrppd.travelCost import costDatabase
from simulator.dpdp_competition.algorithm.vrppd.utlis import customer_request_combination, \
    feasibleRearrangePortAssignmentSchedule

import simulator.dpdp_competition.algorithm.vrppd.getConfig

gConfig = simulator.dpdp_competition.algorithm.vrppd.getConfig.get_config()


class vehicle(object):
    def __init__(self,
                 vehicleID,
                 capacity,
                 position,
                 gps_id,
                 currentVolume=0,
                 status='off_duty'):
        """
        :param vehicleID:
        :param capacity:
        :param position:
        :param route:
            [{"customer", request, "time_window", "arrive_time", "waiting_timespan", "processingTimespan", "departure_time"}, {}, ...]
        :param currentVolume:
        :param status: "idle, en_route, serving, off_duty"
        """
        self._vehicleID = vehicleID
        self._capacity = capacity
        self._route = []
        self._depotID = gps_id
        self._currentVolume = currentVolume
        self._status = status
        self._position = position
        self._finishServedCustomerList = []
        self._staticServeTimeOnCustomer = gConfig["static_process_time_on_customer"]
        self._currentTravelCost = 0
        self._update_time = None
        # self._travelCost_solver = costDatabase()

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
    def getCurrentRouteCost(self, travelCost_solver=costDatabase()):
        return self._currentTravelCost

    def set_update_time(self, Time):
        self._update_time = Time

    def updateTravelCost(self, travelCost_solver):
        if len(self._route) > 1:
            total_distance = 0
            total_travelTime = 0
            for index in range(len(self._route) - 1):
                node1, node2 = self._route[index], self._route[index + 1]
                travel_cost = travelCost_solver.getTravelCost(node1.customerID, node2.customerID)
                total_distance += travel_cost["distance"]
                total_travelTime += travel_cost["travel_time"]
            weight = gConfig["weighted_objective_function"]
            self._currentTravelCost = weight * total_distance + (1 - weight) * total_travelTime
        else:
            self._currentTravelCost = 0

    def getCurrentVolume(self, route_index):
        currentVolume = 0
        for i in range(route_index):
            currentVolume += self._route[i].volume
        return currentVolume

    def underCapacity(self):
        volume = 0
        if len(self._route) > 1:
            for i in range(len(self._route)):
                volume += self._route[i].volume
                if volume > self._capacity:
                    return False
        return True

    def setPDNodeConnection(self, pickup_routeIndex: int, delivery_routeIndex: int):
        """
        用于后续领域搜索，快速找到PD在路径中的位置
        :param pickup_routeIndex:
        :param delivery_routeIndex:
        :return:
        """
        self._route[pickup_routeIndex].setBrotherNodeRouteIndex(delivery_routeIndex)
        self._route[delivery_routeIndex].setBrotherNodeRouteIndex(pickup_routeIndex)

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

    def addNode2Route(self, node: customer_request_combination, index: int):
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
                          customers: Dict[str, customer],
                          customer_id: str,
                          demand_type: str,
                          vehicleArriveTime: datetime,
                          requestID: str,
                          request: dict,
                          node_index_in_route: int) -> bool:
        """
        可能需要递归，因为每次新插入需求会影响很多站点的卡位分配情况
        :return: bool
        """
        brother_customer_id = request[demand_type + "_demand_info"]["brother_customer"]
        node = customer_request_combination(customer_id,
                                            requestID,
                                            demand_type,
                                            brother_customer_id,
                                            request[demand_type + "_demand_info"]["volume"],
                                            request[demand_type + "_demand_info"]["time_window"],
                                            request[demand_type + "_demand_info"]["process_time"],
                                            self._vehicleID)
        node.setVehicleArriveTime(vehicleArriveTime)
        self.addNode2Route(node, node_index_in_route)
        if node_index_in_route > 0:
            self._route[node_index_in_route].setLeftNode(self._route[node_index_in_route - 1])
            self._route[node_index_in_route - 1].setRightNode(self._route[node_index_in_route])
        if node_index_in_route < len(self._route) - 1:
            self._route[node_index_in_route].setRightNode(self._route[node_index_in_route + 1])
            self._route[node_index_in_route + 1].setLeftNode(self._route[node_index_in_route])
        if requestID not in customers[customer_id].getUnfinishedDemands:
            customers[customer_id].addNewDemand(requestID, request[demand_type + "_demand_info"])
        self.updateVolume(request[demand_type + "_demand_info"]["volume"])

        if demand_type == "delivery" and not self.underCapacity():  # 因为PD问题的特殊性，需要在delivery插入后，对载重约束再做一次判断
            return False

        # if customers[customer_id].feasibleReservePort(self, node_index_in_route):
        #     return True
        # else:
        #     pass
        if node.requestID not in customers[node.customerID].getDispatchedRequestSet:
            customers[node.customerID].getDispatchedRequestSet[node.requestID] = node
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

    def resetDepot(self, destination_info, customers):
        """
        如果当前车辆为有任务状态（有目的地点，且目的地点必须要执行），则需要将目的地作为整个路径的起始点来做规划
        :return:
        """
        self._status = "busy"
        depot_node = customer_request_combination(destination_info.customerID,
                                                  destination_info.requestID,
                                                  "depot",
                                                  None,
                                                  destination_info.volume,
                                                  destination_info.timeWindow,
                                                  destination_info.processTime,
                                                  self._vehicleID)
        depot_node.setVehicleArriveTime(destination_info.arriveTime)
        customers[depot_node.customerID].getDispatchedRequestSet[depot_node.requestID] = depot_node
        feasibleRearrangePortAssignmentSchedule(customers, destination_info.customerID, depot_node)
        self._route.append(depot_node)

    def gen_fix_route(self,
                      customers,
                      request_id_on_order,
                      ongoing_items_map,
                      requests_items_map,
                      travelCost_solver=costDatabase()):
        while request_id_on_order:
            requestID = request_id_on_order.pop()
            customerID = ongoing_items_map[requests_items_map[requestID]["delivery_only"][0]]["delivery_factory_id"]
            volume, process_time = 0, 0
            time_window_left, time_window_right = None, None
            for item_id in requests_items_map[requestID]["delivery_only"]:
                volume -= ongoing_items_map[item_id]["demand"]
                process_time += ongoing_items_map[item_id]["unload_time"]
                if not time_window_left and not time_window_right:
                    creation_time = ongoing_items_map[item_id]["creation_time"]
                    committed_completion_time = ongoing_items_map[item_id]["committed_completion_time"]
                    creation_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(creation_time))
                    committed_completion_time = time.strftime("%Y-%m-%d %H:%M:%S",
                                                              time.localtime(committed_completion_time))
                    time_window_left = creation_time
                    time_window_right = committed_completion_time
            node = customer_request_combination(customerID,
                                                requestID,
                                                "delivery",
                                                None,
                                                volume,
                                                [time_window_left, time_window_right],
                                                process_time,
                                                self._vehicleID)
            left_node = self._route[len(self._route) - 1]
            travel_cost = travelCost_solver.getTravelCost(left_node.customerID, customerID)
            arrive_time = left_node.vehicleDepartureTime + timedelta(seconds=travel_cost["travel_time"])
            node.setVehicleArriveTime(arrive_time)
            left_node.setRightNode(node)
            node.setLeftNode(left_node)
            self._route.append(node)
            self.updateVolume(volume)
            if node.requestID not in customers[node.customerID].getDispatchedRequestSet:
                customers[node.customerID].getDispatchedRequestSet[node.requestID] = node
            if not feasibleRearrangePortAssignmentSchedule(customers, customerID, node):
                print("固定路线生成失败？？？？？？？？")

    def activateVehicle(self, volume=0):
        self._status = 'idle'
        depot_node = customer_request_combination(self._depotID,
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
