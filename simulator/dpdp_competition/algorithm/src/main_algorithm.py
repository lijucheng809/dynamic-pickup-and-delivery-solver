import json
import sys
from datetime import datetime, timedelta
import time

from simulator.dpdp_competition.algorithm.src.customer import customer
from simulator.dpdp_competition.algorithm.src.DVRPPDSolver import DVRPPD_Solver
from simulator.dpdp_competition.algorithm.src.vehicle import vehicle
from simulator.dpdp_competition.algorithm.data_transfomer import data_transfomer
from simulator.dpdp_competition.algorithm.src.travelCost import costDatabase
from simulator.dpdp_competition.algorithm.conf.configs import configs

import simulator.dpdp_competition.algorithm.src.getConfig

gConfig = simulator.dpdp_competition.algorithm.src.getConfig.get_config()


def pushRequests2Solver(dvrppd_Solver, order_id_info_map, customer_id_info_map):
    # tips = 1  # 取前六个需求做测试
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
            pickupCustomerObject = customer(pickupCustomerPosition, pickupCustomerID, pickupCustomerPortNum)
            dvrppd_Solver.addCustomer2Pool({order_id_info_map[orderID]["pickup_customer_id"]: pickupCustomerObject})
        else:
            pickupCustomerObject = dvrppd_Solver.getCustomerObject(order_id_info_map[orderID]["pickup_customer_id"])
        if order_id_info_map[orderID]["delivery_customer_id"] not in dvrppd_Solver.getCustomerPool:
            deliveryCustomerID, deliveryCustomerPosition, deliveryCustomerPortNum = \
                getPDCustomerInfo("delivery_customer_id")
            deliveryCustomerObject = customer(deliveryCustomerPosition, deliveryCustomerID, deliveryCustomerPortNum)
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
        dvrppd_Solver.addNewRequest2RequestsPool(request)


def __gen_customer_object(dvrppd_Solver, customerID, customer_id_info_map):
    position = [customer_id_info_map[customerID]["lng"], customer_id_info_map[customerID]["lat"]]
    customerObject = customer(position, customerID, customer_id_info_map[customerID]["port_num"])
    dvrppd_Solver.addCustomer2Pool({customerID: customerObject})


def pushVehicle2Solver(vehicles_info, dvrppd_Solver, customer_id_info_map, ongoing_items_map, request_info):
    requests_items_map = {}
    next_period_vehicle_go_time = None
    for vehicle_info in vehicles_info:
        vehicleID = vehicle_info["id"]
        capacity = vehicle_info["capacity"]
        update_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(vehicle_info["update_time"]))
        time_now = datetime.strptime(update_time, "%Y-%m-%d %H:%M:%S")
        time2Go = time_now + timedelta(minutes=gConfig["time_2_go"])
        if not next_period_vehicle_go_time:
            next_period_vehicle_go_time = time2Go
        customerID = None
        position = None
        if vehicle_info["cur_factory_id"] and vehicle_info["cur_factory_id"] not in dvrppd_Solver.getCustomerPool:
            __gen_customer_object(dvrppd_Solver, vehicle_info["cur_factory_id"], customer_id_info_map)
        if vehicle_info["destination"] and vehicle_info["destination"][
            "factory_id"] not in dvrppd_Solver.getCustomerPool:
            __gen_customer_object(dvrppd_Solver, vehicle_info["destination"]["factory_id"], customer_id_info_map)
        if not vehicle_info["destination"] and not vehicle_info["carrying_items"]:
            leave_time = time.strftime("%Y-%m-%d %H:%M:%S",
                                       time.localtime(vehicle_info["leave_time_at_current_factory"]))
            leave_time = datetime.strptime(leave_time, "%Y-%m-%d %H:%M:%S")
            customerID = vehicle_info["cur_factory_id"]
            position = [customer_id_info_map[customerID]["lng"], customer_id_info_map[customerID]["lat"]]
            vehicleObject = vehicle(vehicleID, capacity, position, customerID)
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
                travel_cost = costDatabase().getTravelCost(vehicle_info["cur_factory_id"],
                                                           vehicle_info["destination"]["factory_id"])
                mileage = -travel_cost["distance"]
            for item_id in carrying_items:
                order_id = ongoing_items_map[item_id]["order_id"]
                order_id_temp = order_id
                if order_id_temp in request_info["requests_items_map"]:
                    order_id_temp = order_id_temp + vehicleID
                if order_id_temp not in request_id_on_order:
                    request_id_on_order.append(order_id_temp)
                if order_id not in requests_items_map_temp:
                    requests_items_map_temp[order_id] = {"delivery_only": []}
                requests_items_map_temp[order_id]["delivery_only"].append(item_id)
                if ongoing_items_map[item_id]["delivery_factory_id"] not in dvrppd_Solver.getCustomerPool:
                    __gen_customer_object(dvrppd_Solver,
                                          ongoing_items_map[item_id]["delivery_factory_id"],
                                          customer_id_info_map)
                load_volume += ongoing_items_map[item_id]["demand"]
            for order_id in requests_items_map_temp:
                if order_id in requests_items_map:
                    order_id_new = order_id + vehicleID
                    requests_items_map[order_id_new] = requests_items_map_temp[order_id]
                else:
                    requests_items_map[order_id] = requests_items_map_temp[order_id]
            arrive_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(vehicle_info["destination"]["arrive_time"]))
            arrive_time = datetime.strptime(arrive_time, "%Y-%m-%d %H:%M:%S")
            customerID = vehicle_info["destination"]["factory_id"]
            position = [customer_id_info_map[customerID]["lng"], customer_id_info_map[customerID]["lat"]]
            vehicleObject = vehicle(vehicleID, capacity, position, customerID, mileage=0)
            vehicleObject.activateVehicle(volume=load_volume)
            vehicleObject.getCurrentRoute[0].setVehicleArriveTime(arrive_time)
            vehicleObject.getCurrentRoute[0].setVehicleDepartureTime(arrive_time)
            dvrppd_Solver.addVehicle2Pool({vehicle_info["id"]: vehicleObject})
            dvrppd_Solver.getVehiclesPool[vehicleID].gen_fix_route(dvrppd_Solver.getCustomerPool,
                                                                   request_id_on_order,
                                                                   ongoing_items_map,
                                                                   requests_items_map)

    request_info["requests_items_map"].update(requests_items_map)
    return next_period_vehicle_go_time


def scheduling():
    start_time = time.time()
    dvrppd_Solver = DVRPPD_Solver()
    with open(configs.customer_info_path,  "r") as f:
        customer_id_info_map = json.load(f)
    with open(configs.vehicle_info_path, "r") as f:
        vehicles_info = json.load(f)
    with open(configs.ongoing_items_path, "r") as f:
        ongoing_items = json.load(f)
    ongoing_items_map = {}
    for item in ongoing_items:
        ongoing_items_map[item["id"]] = item
    vehicles_info_map = {}
    for vehicle_info in vehicles_info:
        vehicles_info_map[vehicle_info["id"]] = vehicle_info
    request_info = data_transfomer.__requests_sim_2_algo()
    pushRequests2Solver(dvrppd_Solver, request_info["requests"], customer_id_info_map)
    time_2_go = pushVehicle2Solver(vehicles_info, dvrppd_Solver, customer_id_info_map, ongoing_items_map, request_info)
    # print(time_2_go)
    # print(request_info["requests"])
    dvrppd_Solver.constructEngine(time2Go=time_2_go)  # 构造解
    middle_tim = time.time()
    left_time_2_heuristic = gConfig["algo_run_time"] - (middle_tim - start_time) / 60. - 0.5  # 留0.5秒输出数据
    if len(request_info["requests"]) > 5:
        dvrppd_Solver.heuristicEngine(time2Go=time_2_go, CPU_limit=left_time_2_heuristic)
    # dvrppd_Solver.foliumPlot(customer_id_info_map)
    vehicle_route = dvrppd_Solver.getVehiclesPool
    customers = dvrppd_Solver.getCustomerPool
    data_transfomer.__solution_algo_2_sim(vehicle_route,
                                          customers,
                                          request_info["requests_items_map"],
                                          vehicles_info_map,
                                          ongoing_items)


if __name__ == "__main__":
    scheduling()
