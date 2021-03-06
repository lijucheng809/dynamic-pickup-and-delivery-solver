import json
import sys
from typing import List, Dict
from datetime import datetime, timedelta
import time
import os

from simulator.dpdp_competition.algorithm.src.customer import Customer
from simulator.dpdp_competition.algorithm.src.TravelCost import CostDatabase
from simulator.dpdp_competition.algorithm.src.utlis import CustomerRequestCombination, \
    feasibleRearrangePortAssignmentSchedule
from simulator.dpdp_competition.algorithm.conf.configs import Configs


class Vehicle(object):
    def __init__(self,
                 vehicle_id,
                 capacity,
                 position,
                 gps_id,
                 current_volume=0,
                 status='off_duty',
                 mileage=0):
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
        # self._travelCost_solver = costDatabase()

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
    def getCurrentRouteCost(self, travel_cost_solver=CostDatabase()):
        return self._currentTravelCost

    def set_update_time(self, Time):
        self._update_time = Time

    def updateTravelCost(self, travel_cost_solver):
        if len(self._route) > 1:
            total_distance = 0
            total_travel_time = 0
            for index in range(len(self._route) - 1):
                node1, node2 = self._route[index], self._route[index + 1]
                travel_cost = travel_cost_solver.getTravelCost(node1.customerID, node2.customerID)
                total_distance += travel_cost["distance"]
                total_travel_time += travel_cost["travel_time"]
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
        ???????????????????????????????????????PD?????????????????????
        :param pickup_route_index:
        :param delivery_route_index:
        :return:
        """
        self._route[pickup_route_index].setBrotherNodeRouteIndex(delivery_route_index)
        self._route[delivery_route_index].setBrotherNodeRouteIndex(pickup_route_index)

    def deleteNodeFromRoute(self, pickup_node_index):
        # ????????????????????? ????????????Pickup??????delivery??????
        pickup_node = self._route[pickup_node_index]
        delivery_node = pickup_node.brotherNode
        self._route.remove(pickup_node)
        self._route.remove(delivery_node)
        # ????????????node???????????????
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
                          request_id: str,
                          request: dict,
                          node_index_in_route: int) -> bool:
        """
        ??????????????????????????????????????????????????????????????????????????????????????????
        :return: bool
        """
        brother_customer_id = request[demand_type + "_demand_info"]["brother_customer"]
        node = CustomerRequestCombination(customer_id,
                                          request_id,
                                          demand_type,
                                          brother_customer_id,
                                          request[demand_type + "_demand_info"]["volume"],
                                          request[demand_type + "_demand_info"]["time_window"],
                                          request[demand_type + "_demand_info"]["process_time"],
                                          self._vehicleID)
        node.setVehicleArriveTime(vehicle_arrive_time)
        self.addNode2Route(node, node_index_in_route)
        if node_index_in_route > 0:
            self._route[node_index_in_route].setLeftNode(self._route[node_index_in_route - 1])
            self._route[node_index_in_route - 1].setRightNode(self._route[node_index_in_route])
        if node_index_in_route < len(self._route) - 1:
            self._route[node_index_in_route].setRightNode(self._route[node_index_in_route + 1])
            self._route[node_index_in_route + 1].setLeftNode(self._route[node_index_in_route])
        if request_id not in customers[customer_id].getUnfinishedDemands:
            customers[customer_id].addNewDemand(request_id, request[demand_type + "_demand_info"])
        self.updateVolume(request[demand_type + "_demand_info"]["volume"])

        if demand_type == "delivery" and not self.underCapacity():  # ??????PD??????????????????????????????delivery?????????????????????????????????????????????
            return False

        if node.requestID not in customers[node.customerID].getDispatchedRequestSet:
            customers[node.customerID].getDispatchedRequestSet[node.requestID] = node
        assert not customers[node.customerID].getDispatchedRequestSet[node.requestID].brotherNode
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
        ????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????
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
        feasibleRearrangePortAssignmentSchedule(customers, destination_info.customerID, depot_node)
        self._route.append(depot_node)

    def gen_fix_route(self,
                      customers,
                      request_id_on_order,
                      ongoing_items_map,
                      requests_items_map,
                      travelCost_solver=CostDatabase()):
        time_out_requests = {}
        if os.path.exists(Configs.time_out_requests):
            with open(Configs.time_out_requests, "r") as f:
                time_out_requests = json.load(f)
        while request_id_on_order:
            requestID = request_id_on_order.pop()
            customerID = ongoing_items_map[requests_items_map[requestID]["delivery_only"][0]]["delivery_factory_id"]
            volume, process_time = 0, 0
            time_window_left, time_window_right = None, None
            for item_id in requests_items_map[requestID]["delivery_only"]:
                volume -= ongoing_items_map[item_id]["demand"]
                process_time += ongoing_items_map[item_id]["unload_time"]
                creation_time = ongoing_items_map[item_id]["creation_time"]
                committed_completion_time = ongoing_items_map[item_id]["committed_completion_time"]
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
                        time_window_right = time_out_requests[requestID_temp]["pickup_demand_info"]["time_window"][1]
                else:
                    time_window_left = max(creation_time, time_window_left)
                    time_window_right = min(committed_completion_time, time_window_right)
            # requestID = requestID + "_ongoing"
            node = CustomerRequestCombination(customerID,
                                              requestID,
                                                "delivery",
                                              None,
                                              volume,
                                              [str(time_window_left), str(time_window_right)],
                                              process_time,
                                              self._vehicleID)
            left_node = self._route[len(self._route) - 1]
            travel_cost = travelCost_solver.getTravelCost(left_node.customerID, customerID)
            arrive_time = left_node.vehicleDepartureTime + timedelta(seconds=travel_cost["travel_time"])
            # print("vehicleID:", self._vehicleID, " requestID:", requestID, " arrive_time:",arrive_time)
            node.setVehicleArriveTime(arrive_time)
            left_node.setRightNode(node)
            node.setLeftNode(left_node)
            self._route.append(node)
            self.updateVolume(volume)
            if node.requestID not in customers[node.customerID].getDispatchedRequestSet:
                customers[node.customerID].getDispatchedRequestSet[node.requestID] = node
            flag = feasibleRearrangePortAssignmentSchedule(customers, customerID, node, tp="gen_fixed_route")
            if not flag:
                # assert flag
                print("????????????????????????, requestID:", node.requestID, file=sys.stderr)

    def force_insertion(self, request, customers, travelCost_solver=CostDatabase()):
        pickup_customer_id = request["pickup_demand_info"]["customer_id"]
        delivery_customer_id = request["delivery_demand_info"]["customer_id"]
        requestID = request["requestID"]
        process_time = request["pickup_demand_info"]["process_time"]
        volume = request["pickup_demand_info"]["volume"]
        time_window_left = request["pickup_demand_info"]["time_window"][0]
        time_window_right = request["pickup_demand_info"]["time_window"][1]
        pickup_node = CustomerRequestCombination(pickup_customer_id,
                                                 requestID,
                                                   "pickup",
                                                 None,
                                                 volume,
                                                 [time_window_left, time_window_right],
                                                 process_time,
                                                 self._vehicleID)
        left_node = self._route[len(self._route) - 1]
        travel_cost = travelCost_solver.getTravelCost(left_node.customerID, pickup_customer_id)
        arrive_time = left_node.vehicleDepartureTime + timedelta(seconds=travel_cost["travel_time"])
        pickup_node.setVehicleArriveTime(arrive_time)
        departure_time = arrive_time + timedelta(seconds=1800+process_time)
        pickup_node.setVehicleDepartureTime(departure_time)
        left_node.setRightNode(pickup_node)
        pickup_node.setLeftNode(left_node)
        self._route.append(pickup_node)
        delivery_node = CustomerRequestCombination(delivery_customer_id,
                                                   requestID,
                                                     "delivery",
                                                   None,
                                                   -volume,
                                                   [time_window_left, time_window_right],
                                                   process_time,
                                                   self._vehicleID)
        left_node = self._route[len(self._route) - 1]
        travel_cost = travelCost_solver.getTravelCost(left_node.customerID, delivery_customer_id)
        arrive_time = left_node.vehicleDepartureTime + timedelta(seconds=travel_cost["travel_time"])
        delivery_node.setVehicleArriveTime(arrive_time)
        departure_time = arrive_time + timedelta(seconds=1800 + process_time)
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
