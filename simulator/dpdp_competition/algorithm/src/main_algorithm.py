import json
import sys
from datetime import datetime, timedelta
import time
import os
from copy import deepcopy
import math

from simulator.dpdp_competition.algorithm.src.customer import Customer
from simulator.dpdp_competition.algorithm.src.DVRPPDSolver import DVRPPDSolver
from simulator.dpdp_competition.algorithm.src.vehicle import Vehicle
from simulator.dpdp_competition.algorithm.data_transfomer import data_transfomer
from simulator.dpdp_competition.algorithm.src.TravelCost import CostDatabase
from simulator.dpdp_competition.algorithm.conf.configs import Configs
from simulator.dpdp_competition.algorithm.src.utlis import CustomerRequestCombination, \
    feasibleRearrangePortAssignmentSchedule
from simulator.dpdp_competition.algorithm.src.request_cluster import cluster, ongoing_request_cluster


def pushRequests2Solver(dvrppd_Solver, order_id_info_map, customer_id_info_map):
    # tips = 1  # 取前六个需求做测试
    time_out_requests = {}
    # if os.path.exists(configs.time_out_requests):
    #     with open(configs.time_out_requests, "r") as f:
    #         time_out_requests = json.load(f)
    for orderID in order_id_info_map:
        # if tips == 5:
        #     break
        # tips += 1

        def getPDCustomerInfo(PD_customer_id):
            customer_info = customer_id_info_map[order_id_info_map[orderID][PD_customer_id]]
            customerID = order_id_info_map[orderID][PD_customer_id]
            customerPosition = [customer_info["lng"], customer_info["lat"]]
            customerPortNum = customer_info["port_num"]
            return customerID, customerPosition, customerPortNum

        if order_id_info_map[orderID]["pickup_customer_id"] not in dvrppd_Solver.getCustomerPool:
            pickupCustomerID, pickupCustomerPosition, pickupCustomerPortNum = \
                getPDCustomerInfo("pickup_customer_id")
            pickupCustomerObject = Customer(pickupCustomerPosition, pickupCustomerID, pickupCustomerPortNum)
            dvrppd_Solver.addCustomer2Pool({order_id_info_map[orderID]["pickup_customer_id"]: pickupCustomerObject})
        else:
            pickupCustomerObject = dvrppd_Solver.getCustomerObject(order_id_info_map[orderID]["pickup_customer_id"])
        if order_id_info_map[orderID]["delivery_customer_id"] not in dvrppd_Solver.getCustomerPool:
            deliveryCustomerID, deliveryCustomerPosition, deliveryCustomerPortNum = \
                getPDCustomerInfo("delivery_customer_id")
            deliveryCustomerObject = Customer(deliveryCustomerPosition, deliveryCustomerID, deliveryCustomerPortNum)
            dvrppd_Solver.addCustomer2Pool(
                {order_id_info_map[orderID]["delivery_customer_id"]: deliveryCustomerObject})
        else:
            deliveryCustomerObject = dvrppd_Solver.getCustomerObject(
                order_id_info_map[orderID]["delivery_customer_id"])
        # demandInfo: creation_time, demandType, volume, brotherCustomer, timeWindow, finishTime, matchedVehicle
        creation_time = datetime.strptime(order_id_info_map[orderID]["creation_time"], "%Y-%m-%d %H:%M:%S")
        pickupDemandInfo = {"creation_time": creation_time,
                            "customer_id": order_id_info_map[orderID]["pickup_customer_id"],
                            "demand_type": "pickup",
                            "volume": (order_id_info_map[orderID]["pallets"]["q_standard"] +
                                       order_id_info_map[orderID]["pallets"]["q_small"] +
                                       order_id_info_map[orderID]["pallets"]["q_box"]),
                            "brother_customer": order_id_info_map[orderID]["pickup_customer_id"],
                            "time_window": order_id_info_map[orderID]["pickup_timeWindow"],
                            "process_time": order_id_info_map[orderID]["load/unload_time"],
                            "finish_time": None,
                            "matchedVehicle": None}
        deliveryDemandInfo = {"creation_time": creation_time,
                              "customer_id": order_id_info_map[orderID]["delivery_customer_id"],
                              "demand_type": "delivery",
                              "volume": -(order_id_info_map[orderID]["pallets"]["q_standard"] +
                                          order_id_info_map[orderID]["pallets"]["q_small"] +
                                          order_id_info_map[orderID]["pallets"]["q_box"]),
                              "brother_customer": order_id_info_map[orderID]["delivery_customer_id"],
                              "time_window": order_id_info_map[orderID]["delivery_timeWindow"],
                              "process_time": order_id_info_map[orderID]["load/unload_time"],
                              "finish_time": None,
                              "matchedVehicle": None}
        pickupCustomerObject.addNewDemand(orderID, pickupDemandInfo)
        deliveryCustomerObject.addNewDemand(orderID, deliveryDemandInfo)
        request = {orderID: {"requestID": orderID,
                             "pickup_demand_info": pickupDemandInfo,
                             "delivery_demand_info": deliveryDemandInfo,
                             "creation_time": order_id_info_map[orderID]["creation_time"],
                             "finish_time": None}}
        # if orderID in time_out_requests:
        #     request[orderID]["pickup_demand_info"]["time_window"][1] = time_out_requests[orderID]["pickup_demand_info"]["time_window"][1]
        #     request[orderID]["delivery_demand_info"]["time_window"][1]= time_out_requests[orderID]["delivery_demand_info"]["time_window"][1]
        # else:
        #     if "-" in orderID:
        #         index_ = orderID.index("-")
        #         orderID_new = orderID[:index_]
        #         if orderID_new in time_out_requests:
        #             request[orderID]["pickup_demand_info"]["time_window"][1] = \
        #                 time_out_requests[orderID_new]["pickup_demand_info"]["time_window"][1]
        #             request[orderID]["delivery_demand_info"]["time_window"][1] = \
        #                 time_out_requests[orderID_new]["delivery_demand_info"]["time_window"][1]
        dvrppd_Solver.addNewRequest2RequestsPool(request)


def __gen_customer_object(dvrppd_Solver, customerID, customer_id_info_map):
    position = [customer_id_info_map[customerID]["lng"], customer_id_info_map[customerID]["lat"]]
    customerObject = Customer(position, customerID, customer_id_info_map[customerID]["port_num"])
    dvrppd_Solver.addCustomer2Pool({customerID: customerObject})


def pushVehicle2Solver(vehicles_info, dvrppd_Solver, customer_id_info_map, ongoing_items_map, request_info,
                       middle_vehicle_info):
    requests_items_map = {}
    next_period_vehicle_go_time = None
    for vehicle_info in vehicles_info:
        vehicleID = vehicle_info["id"]
        capacity = vehicle_info["capacity"]
        update_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(vehicle_info["update_time"]))
        time_now = datetime.strptime(update_time, "%Y-%m-%d %H:%M:%S")
        # time2Go = time_now + timedelta(minutes=gConfig["time_2_go"])
        time2Go = time_now
        if not next_period_vehicle_go_time:
            next_period_vehicle_go_time = time2Go
        customerID = None
        position = None
        if vehicle_info["cur_factory_id"] and vehicle_info["cur_factory_id"] not in dvrppd_Solver.getCustomerPool:
            __gen_customer_object(dvrppd_Solver, vehicle_info["cur_factory_id"], customer_id_info_map)
        if vehicle_info["destination"] and vehicle_info["destination"][
            "factory_id"] not in dvrppd_Solver.getCustomerPool:
            __gen_customer_object(dvrppd_Solver, vehicle_info["destination"]["factory_id"], customer_id_info_map)
        if vehicle_info["cur_factory_id"] and vehicle_info["carrying_items"]:
            customerID = vehicle_info["cur_factory_id"]
            if vehicle_info["carrying_items"]:
                for item_id in vehicle_info["carrying_items"]:
                    order_id = ongoing_items_map[item_id]["order_id"] + vehicleID
                    break
                requestID = order_id + vehicleID
                time_window_left = time.strftime("%Y-%m-%d %H:%M:%S",
                                                 time.localtime(vehicle_info["arrive_time_at_current_factory"]))
                time_window_left = datetime.strptime(time_window_left, "%Y-%m-%d %H:%M:%S")
                time_window_right = time.strftime("%Y-%m-%d %H:%M:%S",
                                                  time.localtime(vehicle_info["leave_time_at_current_factory"]))
                time_window_right = datetime.strptime(time_window_right, "%Y-%m-%d %H:%M:%S")
                process_time = (time_window_right - time_window_left).seconds
                node = CustomerRequestCombination(customerID,
                                                  requestID,
                                                    "parking",
                                                  None,
                                                  0,
                                                  [str(time_window_left), str(time_window_right)],
                                                  process_time,
                                                  vehicleID)
                node.setVehicleArriveTime(time_window_left)
                if node.requestID not in dvrppd_Solver.getCustomerPool[node.customerID].getDispatchedRequestSet:
                    dvrppd_Solver.getCustomerPool[node.customerID].getDispatchedRequestSet[node.requestID] = node
                feasibleRearrangePortAssignmentSchedule(dvrppd_Solver.getCustomerPool, customerID, node)
        if not vehicle_info["destination"] and not vehicle_info["carrying_items"]:
            customerID = vehicle_info["cur_factory_id"]
            leave_time = time.strftime("%Y-%m-%d %H:%M:%S",
                                       time.localtime(vehicle_info["leave_time_at_current_factory"]))
            leave_time = datetime.strptime(leave_time, "%Y-%m-%d %H:%M:%S")
            position = [customer_id_info_map[customerID]["lng"], customer_id_info_map[customerID]["lat"]]
            vehicleObject = Vehicle(vehicleID, capacity, position, customerID)
            vehicleObject.activateVehicle(volume=0)
            if leave_time > time2Go:
                time2Go = leave_time
            vehicleObject.getCurrentRoute[0].setVehicleArriveTime(time2Go)
            vehicleObject.getCurrentRoute[0].setVehicleDepartureTime(time2Go)
            dvrppd_Solver.addVehicle2Pool({vehicle_info["id"]: vehicleObject})
        else:
            load_volume = 0
            requests_items_map_temp = {}
            carrying_items = vehicle_info["carrying_items"]
            request_id_on_order = []  # 存放将来生成固定线路的node顺序
            mileage = 0
            if vehicle_info["cur_factory_id"] and vehicle_info["destination"]:
                travel_cost = CostDatabase().getTravelCost(vehicle_info["cur_factory_id"],
                                                           vehicle_info["destination"]["factory_id"])
                mileage = travel_cost["distance"]
            elif not vehicle_info["cur_factory_id"] and vehicle_info["destination"]:
                travel_cost = CostDatabase().getTravelCost(middle_vehicle_info[vehicleID]["start"],
                                                           vehicle_info["destination"]["factory_id"])
                mileage = travel_cost["distance"]
            for item_id in carrying_items:
                order_id = ongoing_items_map[item_id]["order_id"] + vehicleID
                if order_id not in request_id_on_order:
                    request_id_on_order.append(order_id)
                if order_id not in requests_items_map_temp:
                    requests_items_map_temp[order_id] = {"delivery_only": []}
                requests_items_map_temp[order_id]["delivery_only"].append(item_id)
                if ongoing_items_map[item_id]["delivery_factory_id"] not in dvrppd_Solver.getCustomerPool:
                    __gen_customer_object(dvrppd_Solver,
                                          ongoing_items_map[item_id]["delivery_factory_id"],
                                          customer_id_info_map)
                load_volume += ongoing_items_map[item_id]["demand"]
            # TODO 对载货订单进行聚类
            new_request_id_on_order, new_requests_items_map = ongoing_request_cluster(request_id_on_order,
                                                                                      requests_items_map_temp,
                                                                                      ongoing_items_map,
                                                                                      vehicleID)
            requests_items_map.update(new_requests_items_map)
            # requests_items_map.update(requests_items_map_temp)
            arrive_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(vehicle_info["destination"]["arrive_time"]))
            arrive_time = datetime.strptime(arrive_time, "%Y-%m-%d %H:%M:%S")
            customerID = vehicle_info["destination"]["factory_id"]
            position = [customer_id_info_map[customerID]["lng"], customer_id_info_map[customerID]["lat"]]
            vehicleObject = Vehicle(vehicleID, capacity, position, customerID, mileage=mileage)
            vehicleObject.activateVehicle(volume=load_volume)
            vehicleObject.getCurrentRoute[0].setVehicleArriveTime(arrive_time)
            vehicleObject.getCurrentRoute[0].setVehicleDepartureTime(arrive_time)
            dvrppd_Solver.addVehicle2Pool({vehicle_info["id"]: vehicleObject})
            dvrppd_Solver.getVehiclesPool[vehicleID].gen_fix_route(dvrppd_Solver.getCustomerPool,
                                                                   new_request_id_on_order,
                                                                   ongoing_items_map,
                                                                   requests_items_map)

    request_info["requests_items_map"].update(requests_items_map)
    return next_period_vehicle_go_time


def scheduling():
    start_time = time.time()
    middle_vehicle_info = None
    with open(Configs.customer_info_path, "r") as f:
        customer_id_info_map = json.load(f)
    with open(Configs.vehicle_info_path, "r") as f:
        vehicles_info = json.load(f)
    with open(Configs.ongoing_items_path, "r") as f:
        ongoing_items = json.load(f)
    if os.path.exists(Configs.middle_vehicle_info_path):
        with open(Configs.middle_vehicle_info_path, "r") as f:
            middle_vehicle_info = json.load(f)
    time_out_requests = {}
    if os.path.exists(Configs.time_out_requests):
        with open(Configs.time_out_requests, "r") as f:
            time_out_requests = json.load(f)
    ongoing_items_map = {}
    for item in ongoing_items:
        ongoing_items_map[item["id"]] = item
    vehicles_info_map = {}
    for vehicle_info in vehicles_info:
        vehicles_info_map[vehicle_info["id"]] = vehicle_info

    request_info = data_transfomer.__requests_sim_2_algo()
    for requestID in request_info["requests"]:
        if requestID in time_out_requests:
            request_info["requests"][requestID]["pickup_timeWindow"][1] = \
                time_out_requests[requestID]["pickup_demand_info"]["time_window"][1]
            request_info["requests"][requestID]["delivery_timeWindow"][1] = \
                time_out_requests[requestID]["delivery_demand_info"]["time_window"][1]
        else:
            if "-" in requestID:
                index_ = requestID.index("-")
                orderID_new = requestID[:index_]
                if orderID_new in time_out_requests:
                    request_info["requests"][requestID]["pickup_timeWindow"][1] = \
                        time_out_requests[orderID_new]["pickup_demand_info"]["time_window"][1]
                    request_info["requests"][requestID]["delivery_timeWindow"][1] = \
                        time_out_requests[orderID_new]["delivery_demand_info"]["time_window"][1]
    new_requests, old_requests_map = cluster(deepcopy(request_info["requests"]))
    print(old_requests_map, file=sys.stderr)
    dvrppd_Solver = DVRPPDSolver(old_requests_map)
    pushRequests2Solver(dvrppd_Solver, new_requests, customer_id_info_map)
    time_2_go = pushVehicle2Solver(vehicles_info, dvrppd_Solver, customer_id_info_map, ongoing_items_map,
                                   request_info, middle_vehicle_info)
    flag = True
    for vehicle_info in vehicles_info:
        if vehicle_info["destination"]:
            flag = False
            break
    dvrppd_Solver.constructEngine(time2Go=time_2_go, CPU_limit=Configs.algo_run_time - 1)  # 构造解
    middle_tim = time.time()
    left_time_2_heuristic = Configs.algo_run_time - (middle_tim - start_time) / 60. - 0.5  # 留30秒输出数据
    if len(new_requests) > 10 and left_time_2_heuristic > 3:
        dvrppd_Solver.heuristicEngine(time2Go=time_2_go, CPU_limit=2)
    # dvrppd_Solver.foliumPlot(customer_id_info_map)
    vehicle_route = dvrppd_Solver.getVehiclesPool
    customers = dvrppd_Solver.getCustomerPool
    data_transfomer.__solution_algo_2_sim(vehicle_route,
                                          customers,
                                          request_info["requests_items_map"],
                                          vehicles_info_map,
                                          old_requests_map)


if __name__ == "__main__":
    scheduling()
    # print(datetime.now().timestamp())
