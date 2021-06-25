import random
from typing import Dict
from datetime import datetime, timedelta
import json
import pandas as pd
import numpy as np

from simulator.dpdp_competition.algorithm.src.travelCost import costDatabase


class customer_request_combination(object):
    def __init__(self,
                 customerID,
                 requestID,
                 demandType,
                 brother_customerID,
                 volume,
                 time_window,
                 processTime,
                 vehicleID):
        self.customerID = customerID
        self.requestID = requestID
        self.demandType = demandType
        self.volume = volume
        self.brother_customerID = brother_customerID
        self.timeWindow = time_window
        self.processTime = processTime
        self.vehicleID = vehicleID
        self.vehicleArriveTime = None
        self.startProcessTime = None
        self.vehicleDepartureTime = None
        self.vehicleArriveTime_normal = None
        self.volume_normal = None
        self.leftNode = None
        self.rightNode = None
        self.brotherNode = None

    def __lt__(self, other):
        return self.vehicleArriveTime < other.vehicleArriveTime

    def setNormalVolume(self, volume: float):
        self.volume_normal = volume

    def setNormalArriveTime(self, time: float):
        self.vehicleArriveTime_normal = time

    def setVehicleArriveTime(self, time):
        self.vehicleArriveTime = time

    def setVehicleDepartureTime(self, time):
        self.vehicleDepartureTime = time

    def setLeftNode(self, left_node):
        self.leftNode = left_node

    def setRightNode(self, right_node):
        self.rightNode = right_node

    def setBrotherNode(self, node):
        self.brotherNode = node

    def setStartProcessTime(self, time):
        self.startProcessTime = time


class sourcePool(object):
    def __init__(self, vehicles, customers, requests):
        self.vehicles = vehicles
        self.customers = customers
        self.requests = requests


class destination(object):
    def __init__(self, customerID, requestID, volume, process_time, arrive_time, time_window):
        self.customerID = customerID
        self.requestID = requestID
        self.volume = volume
        self.processTime = process_time
        self.arriveTime = arrive_time
        self.timeWindow = time_window


class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime("%Y-%m-%d %H:%M:%S")
        else:
            return json.JSONEncoder.default(self, obj)


class fileProcessor(object):

    @staticmethod
    def orders_csv_2_json(input_file: str, output_file: str):
        df_order = pd.read_csv(input_file)
        n, m = df_order.shape

        order_id_info_map = dict()
        for i in range(n):
            order_id = str(df_order.iloc[i]["order_id"])
            pallets = {"q_standard": int(df_order.iloc[i]["q_standard"]),
                       "q_small": int(df_order.iloc[i]["q_small"]),
                       "q_box": int(df_order.iloc[i]["q_box"])}
            demand = float(df_order.iloc[i]["demand"])
            creation_time = datetime.strptime(df_order.iloc[i]["creation_time"], "%H:%M:%S")
            committed_completion_time = datetime.strptime(df_order.iloc[i]["committed_completion_time"], "%H:%M:%S")
            tw = [creation_time.strftime("%H:%M:%S"),
                  (committed_completion_time.strftime("%H:%M:%S"))]
            load_unload_time = int(df_order.iloc[i]["load_time"])
            pickup_customer_id = df_order.iloc[i]["pickup_id"]
            delivery_customer_id = df_order.iloc[i]["delivery_id"]
            order_id_info_map[order_id] = {"pallets": pallets,
                                           "demand": demand,
                                           "creation_time": tw[0],
                                           "pickup_timeWindow": tw,
                                           "delivery_timeWindow": tw,
                                           "load/unload_time": load_unload_time,
                                           "delivery_customer_id": delivery_customer_id,
                                           "pickup_customer_id": pickup_customer_id}
        with open(output_file, "w") as f:
            json.dump(order_id_info_map, f, indent=4)

    @staticmethod
    def factories_csv_2_json(input_file: str, output_file: str):
        df_customer = pd.read_csv(input_file)
        n, m = df_customer.shape
        customer_id_info_map = dict()
        for i in range(n):
            customer_id_info_map[df_customer.iloc[i][0]] = {"lng": float(df_customer.iloc[i]["longitude"]),
                                                            "lat": float(df_customer.iloc[i]["latitude"]),
                                                            "port_num": int(df_customer.iloc[i]["port_num"])}
        with open(output_file, "w") as f:
            json.dump(customer_id_info_map, f, indent=4)

    @staticmethod
    def vehicles_csv_2_json(input_file: str, factory_json_file: str,  output_file: str):
        df_vehicle = pd.read_csv(input_file)
        n, m = df_vehicle.shape
        vehicle_id_info_map = dict()
        with open(factory_json_file, "r") as f:
            order_id_info_map = json.load(f)
        vehicle_init_pos_set = random.sample(list(order_id_info_map.keys()), n)
        for i, pos_id in enumerate(vehicle_init_pos_set):
            vehicle_id = df_vehicle.iloc[i]["car_num"]
            vehicle_id_info_map[vehicle_id] = {"capacity": int(df_vehicle.iloc[i]["capacity"]),
                                               "operation_time": int(df_vehicle.iloc[i]["operation_time"]),
                                               "gps_id": pos_id}
        with open(output_file, "w") as f:
            json.dump(vehicle_id_info_map, f, indent=4)

    @staticmethod
    def routeMap_csv_2_json(input_file: str, output_file: str):
        df_route_cost = pd.read_csv(input_file)
        n, m = df_route_cost.shape
        route_cost_map = dict()

        for i in range(n):
            route_cost_map[df_route_cost.iloc[i]["start_factory_id"] + df_route_cost.iloc[i]["end_factory_id"]] \
                = {"distance": float(df_route_cost.iloc[i]["distance"]),
                   "travel_time": int(df_route_cost.iloc[i]["time"])}
        with open(output_file, "w") as f:
            json.dump(route_cost_map, f, indent=4)

    @staticmethod
    def normalizeTravelCost(route_cost_json_file: str):
        max_distance, min_distance = -np.infty, np.infty
        max_travelTime, min_travelTime = -np.infty, np.infty
        with open(route_cost_json_file, "r") as f:
            route_cost_map = json.load(f)
        for pd_pair in route_cost_map:
            max_distance = max(max_distance, route_cost_map[pd_pair]["distance"])
            min_distance = min(min_distance, route_cost_map[pd_pair]["distance"])
            max_travelTime = max(max_travelTime, route_cost_map[pd_pair]["travel_time"])
            min_travelTime = min(min_travelTime, route_cost_map[pd_pair]["travel_time"])

        for pd_pair in route_cost_map:
            route_cost_map[pd_pair]["normal_distance"] = (route_cost_map[pd_pair]["distance"] - min_distance) \
                                                         / (max_distance - min_distance)
            route_cost_map[pd_pair]["normal_travelTime"] = (route_cost_map[pd_pair]["travel_time"] - min_travelTime) \
                                                           / (max_travelTime - min_travelTime)
        with open(route_cost_json_file, "w") as f:
            json.dump(route_cost_map, f, indent=4)


def feasibleRearrangePortAssignmentSchedule(customers: dict,
                                            customerID: str,
                                            node: customer_request_combination,
                                            tp="repair") -> bool:
    # print("递归开始")
    if node.requestID not in customers[customerID].getDispatchedRequestSet:
        customers[customerID].getDispatchedRequestSet[node.requestID] = node
    customers[customerID].clearPortReserveTable()
    rearrange_node_list = customers[customerID].rearrangeReservedPort(tp)
    if rearrange_node_list is None:
        return False
    else:
        if len(rearrange_node_list) == 0:
            return True
        else:
            for nd in rearrange_node_list:
                return feasibleRearrangePortAssignmentSchedule(customers, nd.customerID, nd, tp)


def checker(vehicles):
    flag = True
    # 判断PD_pair是否互相match
    for vehicleID in vehicles:
        route_length = len(vehicles[vehicleID].getCurrentRoute)
        if route_length > 1:
            for index, node in enumerate(vehicles[vehicleID].getCurrentRoute):
                if index > 0 and node.requestID != node.brotherNode.requestID:
                    flag = False
                if index < route_length-1:
                    right_node_arrive_time = node.vehicleDepartureTime \
                                             + timedelta(seconds=costDatabase().getTravelCost(node.customerID,
                                                                                              node.rightNode.customerID)["travel_time"])
                    # if right_node_arrive_time != node.rightNode.vehicleArriveTime:
                    #     print("到达时间有问题！！！！！！！！！！！！！！！！！！！！！！！！！！！！")
                    #     print(right_node_arrive_time, node.rightNode.vehicleArriveTime)
                    #     flag = False
    if not flag:
        # print("brother node 异常")
        pass
    return flag


class checks(object):

    @staticmethod
    def print_solution(vehicles):

        for vehicleID in vehicles:
            if len(vehicles[vehicleID].getCurrentRoute) > 1:
                vehicles[vehicleID].updateTravelCost(costDatabase())
                for index, node in enumerate(vehicles[vehicleID].getCurrentRoute):
                    if index == 0:
                        print("vehicleID: ", vehicleID,
                              "customerID: ", node.customerID,
                              "     arrive_time:", node.vehicleArriveTime,
                              "     leave_time:", node.vehicleDepartureTime)
                    else:
                        dis = costDatabase().getTravelCost(
                            vehicles[
                                vehicleID].getCurrentRoute[
                                index - 1].customerID,
                            node.customerID)
                        if node.customerID == node.leftNode.customerID:
                            diff = 0
                        else:
                            diff = (node.vehicleArriveTime-node.leftNode.vehicleDepartureTime).seconds/60.
                        # assert diff == dis["travel_time"] / 60.
                        print("vehicleID: ", vehicleID,
                              "customerID: ", node.customerID,
                              "     arrive_time:", node.vehicleArriveTime,
                              "     leave_time:", node.vehicleDepartureTime,
                              "travel_time: ", dis["travel_time"] / 60.,
                              "  diff:", diff)
