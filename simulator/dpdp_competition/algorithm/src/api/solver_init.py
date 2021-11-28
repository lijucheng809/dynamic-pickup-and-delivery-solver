import time
from datetime import datetime, timedelta

from simulator.dpdp_competition.algorithm.src.common.customer import Customer
from simulator.dpdp_competition.algorithm.src.common.vehicle import Vehicle
from simulator.dpdp_competition.algorithm.src.utils.utlis import feasibleRearrangePortAssignmentSchedule
from simulator.dpdp_competition.algorithm.src.common.customer_request_combination import CustomerRequestCombination
from simulator.dpdp_competition.algorithm.src.utils.request_cluster_util import RequestCluster
from simulator.dpdp_competition.algorithm.conf.configs import Configs
from simulator.dpdp_competition.algorithm.src.algo.dpdp_solver import DPDPSolver
from simulator.dpdp_competition.algorithm.src.enum.constrain_enum import ConstrainEnum
from simulator.dpdp_competition.algorithm.src.enum.request_info_enum import RequestInfoEnum
from simulator.dpdp_competition.algorithm.src.enum.vehicle_info_enum import VehicleInfoEnum
from simulator.dpdp_competition.algorithm.src.enum.destination_info_enum import DestinationInfoEnum
from simulator.dpdp_competition.algorithm.src.enum.customer_info_enum import CustomerInfoEnum
from simulator.dpdp_competition.algorithm.src.enum.item_info_enum import ItemInfoEnum
from simulator.dpdp_competition.algorithm.src.enum.demand_type_enum import DemandTypeEnum
from simulator.dpdp_competition.algorithm.src.enum.package_enum import PackageEnum
from simulator.dpdp_competition.algorithm.src.enum.demand_info_enum import DemandInfoEnum


class SolverInit(object):
    @staticmethod
    def pushRequests2Solver(dpdp_solver: DPDPSolver, request_id_info_map: dict, customer_id_info_map: dict):
        # tips = 1  # 取前六个需求做测试
        time_out_requests = {}
        # if os.path.exists(configs.time_out_requests):
        #     with open(configs.time_out_requests, "r") as f:
        #         time_out_requests = json.load(f)
        request_id_bin_map = {}

        for request_id in request_id_info_map:
            # if tips == 5:
            #     break
            # tips += 1
            if Configs.constrains[ConstrainEnum.bin_packing]:
                request_id_bin_map[request_id] = request_id_info_map[request_id][RequestInfoEnum.bin_dimension.name]

            def getPDCustomerInfo(PD_customer_id):
                customer_info = customer_id_info_map[request_id_info_map[request_id][PD_customer_id]]
                customerID = request_id_info_map[request_id][PD_customer_id]
                customerPosition = [customer_info[CustomerInfoEnum.lng.name], customer_info[CustomerInfoEnum.lat.name]]
                customerPortNum = customer_info[CustomerInfoEnum.port_num.name]
                return customerID, customerPosition, customerPortNum

            if request_id_info_map[request_id][
                RequestInfoEnum.pickup_customer_id.name] not in dpdp_solver.getCustomerPool:
                pickupCustomerID, pickupCustomerPosition, pickupCustomerPortNum = \
                    getPDCustomerInfo(RequestInfoEnum.pickup_customer_id.name)
                pickupCustomerObject = Customer(pickupCustomerPosition, pickupCustomerID, pickupCustomerPortNum)
                dpdp_solver.addCustomer2Pool(
                    {request_id_info_map[request_id][RequestInfoEnum.pickup_customer_id.name]: pickupCustomerObject})
            else:
                pickupCustomerObject = dpdp_solver.getCustomerObject(
                    request_id_info_map[request_id][RequestInfoEnum.pickup_customer_id.name])
            if request_id_info_map[request_id][
                RequestInfoEnum.delivery_customer_id.name] not in dpdp_solver.getCustomerPool:
                deliveryCustomerID, deliveryCustomerPosition, deliveryCustomerPortNum = \
                    getPDCustomerInfo(RequestInfoEnum.delivery_customer_id.name)
                deliveryCustomerObject = Customer(deliveryCustomerPosition, deliveryCustomerID, deliveryCustomerPortNum)
                dpdp_solver.addCustomer2Pool(
                    {request_id_info_map[request_id][
                         RequestInfoEnum.delivery_customer_id.name]: deliveryCustomerObject})
            else:
                deliveryCustomerObject = dpdp_solver.getCustomerObject(
                    request_id_info_map[request_id][RequestInfoEnum.delivery_customer_id.name])
            # demandInfo: creation_time, demandType, volume, brotherCustomer, timeWindow, finishTime, matchedVehicle
            creation_time = datetime.strptime(request_id_info_map[request_id][RequestInfoEnum.creation_time.name],
                                              "%Y-%m-%d %H:%M:%S")
            pickupDemandInfo = {RequestInfoEnum.creation_time.name: creation_time,
                                DemandInfoEnum.customer_id.name: request_id_info_map[request_id][RequestInfoEnum.pickup_customer_id.name],
                                DemandInfoEnum.demand_type.name: DemandTypeEnum.pickup.name,
                                DemandInfoEnum.volume.name: (request_id_info_map[request_id][RequestInfoEnum.pallets.name][PackageEnum.q_standard.name] +
                                           request_id_info_map[request_id][RequestInfoEnum.pallets.name][PackageEnum.q_small.name] +
                                           request_id_info_map[request_id][RequestInfoEnum.pallets.name][PackageEnum.q_box.name]),
                                DemandInfoEnum.brother_customer.name: request_id_info_map[request_id][
                                    RequestInfoEnum.delivery_customer_id.name],
                                DemandInfoEnum.time_window.name: request_id_info_map[request_id][RequestInfoEnum.pickup_timeWindow.name],
                                DemandInfoEnum.process_time.name: request_id_info_map[request_id][RequestInfoEnum.process_time.name],
                                DemandInfoEnum.finish_time.name: None,
                                DemandInfoEnum.matchedVehicle.name: None}
            deliveryDemandInfo = {RequestInfoEnum.creation_time.name: creation_time,
                                  DemandInfoEnum.customer_id.name: request_id_info_map[request_id][
                                      RequestInfoEnum.delivery_customer_id.name],
                                  DemandInfoEnum.demand_type.name: DemandTypeEnum.delivery.name,
                                  DemandInfoEnum.volume.name: -(request_id_info_map[request_id][RequestInfoEnum.pallets.name][PackageEnum.q_standard.name] +
                                              request_id_info_map[request_id][RequestInfoEnum.pallets.name][PackageEnum.q_small.name] +
                                              request_id_info_map[request_id][RequestInfoEnum.pallets.name][PackageEnum.q_box.name]),
                                  DemandInfoEnum.brother_customer.name: request_id_info_map[request_id][
                                      RequestInfoEnum.pickup_customer_id.name],
                                  DemandInfoEnum.time_window.name: request_id_info_map[request_id][
                                      RequestInfoEnum.delivery_timeWindow.name],
                                  DemandInfoEnum.process_time.name: request_id_info_map[request_id][RequestInfoEnum.process_time.name],
                                  DemandInfoEnum.finish_time.name: None,
                                  DemandInfoEnum.matchedVehicle.name: None}
            pickupCustomerObject.addNewDemand(request_id, pickupDemandInfo)
            deliveryCustomerObject.addNewDemand(request_id, deliveryDemandInfo)
            request = {request_id: {RequestInfoEnum.requestID.name: request_id,
                                    RequestInfoEnum.pickup_demand_info.name: pickupDemandInfo,
                                    RequestInfoEnum.delivery_demand_info.name: deliveryDemandInfo,
                                    RequestInfoEnum.creation_time.name: request_id_info_map[request_id][RequestInfoEnum.creation_time.name],
                                    RequestInfoEnum.finish_time.name: None}}
            if Configs.constrains[ConstrainEnum.bin_packing]:
                dpdp_solver.push_request_bin_map_2_request_pool(request_id_bin_map)
                request[request_id][RequestInfoEnum.bin_dimension.name] = request_id_info_map[request_id][
                    RequestInfoEnum.bin_dimension.name]
            if Configs.constrains[ConstrainEnum.incompatible_items]:
                request[request_id][RequestInfoEnum.incompatible_item_type_list.name] = request_id_info_map[request_id][
                    RequestInfoEnum.incompatible_item_type_list.name]
            dpdp_solver.addNewRequest2RequestsPool(request)
        if Configs.constrains[ConstrainEnum.bin_packing]:
            dpdp_solver.getRequestsPool.gen_request_id_dimension_map()

    @staticmethod
    def __gen_customer_object(dpdp_solver, customer_id, customer_id_info_map):
        position = [customer_id_info_map[customer_id][CustomerInfoEnum.lng.name],
                    customer_id_info_map[customer_id][CustomerInfoEnum.lat.name]]
        customerObject = Customer(position, customer_id,
                                  customer_id_info_map[customer_id][CustomerInfoEnum.port_num.name])
        dpdp_solver.addCustomer2Pool({customer_id: customerObject})

    @staticmethod
    def pushVehicle2Solver(vehicles_info, dpdp_solver, customer_id_info_map, ongoing_items_map, request_info):
        requests_items_map = {}
        for vehicle_info in vehicles_info:
            vehicleID = vehicle_info[VehicleInfoEnum.id.name]
            capacity = vehicle_info[VehicleInfoEnum.capacity.name]
            update_time = time.strftime("%Y-%m-%d %H:%M:%S",
                                        time.localtime(vehicle_info[VehicleInfoEnum.update_time.name]))
            time2_go = datetime.strptime(update_time, "%Y-%m-%d %H:%M:%S")
            # time2Go = time_now + timedelta(minutes=gConfig["time_2_go"])
            customerID = None
            position = None
            if vehicle_info[VehicleInfoEnum.cur_factory_id.name] and vehicle_info[
                VehicleInfoEnum.cur_factory_id.name] not in dpdp_solver.getCustomerPool:
                SolverInit.__gen_customer_object(dpdp_solver, vehicle_info[VehicleInfoEnum.cur_factory_id.name],
                                                 customer_id_info_map)
            if vehicle_info[VehicleInfoEnum.destination.name] and vehicle_info[VehicleInfoEnum.destination.name][
                DestinationInfoEnum.factory_id.name] not in dpdp_solver.getCustomerPool:
                SolverInit.__gen_customer_object(dpdp_solver, vehicle_info[VehicleInfoEnum.destination.name][
                    DestinationInfoEnum.factory_id.name], customer_id_info_map)
            if vehicle_info[VehicleInfoEnum.cur_factory_id.name] and vehicle_info[VehicleInfoEnum.carrying_items.name]:
                customerID = vehicle_info[VehicleInfoEnum.cur_factory_id.name]
                if vehicle_info[VehicleInfoEnum.carrying_items.name]:
                    for item_id in vehicle_info[VehicleInfoEnum.carrying_items.name]:
                        order_id = ongoing_items_map[item_id]["order_id"] + vehicleID
                        break
                    requestID = order_id + vehicleID
                    time_window_left = time.strftime("%Y-%m-%d %H:%M:%S",
                                                     time.localtime(vehicle_info[
                                                                        VehicleInfoEnum.arrive_time_at_current_factory.name]))
                    time_window_left = datetime.strptime(time_window_left, "%Y-%m-%d %H:%M:%S")
                    time_window_right = time.strftime("%Y-%m-%d %H:%M:%S",
                                                      time.localtime(vehicle_info[
                                                                         VehicleInfoEnum.leave_time_at_current_factory.name]))
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
                    if node.requestID not in dpdp_solver.getCustomerPool[node.customerID].getDispatchedRequestSet:
                        dpdp_solver.getCustomerPool[node.customerID].getDispatchedRequestSet[node.requestID] = node
                    if Configs.constrains[ConstrainEnum.port_resource]:
                        feasibleRearrangePortAssignmentSchedule(dpdp_solver.getCustomerPool, customerID, node)
            if not vehicle_info[VehicleInfoEnum.destination.name] and not vehicle_info[
                VehicleInfoEnum.carrying_items.name]:
                customerID = vehicle_info[VehicleInfoEnum.cur_factory_id.name]
                leave_time = time.strftime("%Y-%m-%d %H:%M:%S",
                                           time.localtime(
                                               vehicle_info[VehicleInfoEnum.leave_time_at_current_factory.name]))
                leave_time = datetime.strptime(leave_time, "%Y-%m-%d %H:%M:%S")
                position = [customer_id_info_map[customerID][CustomerInfoEnum.lng.name],
                            customer_id_info_map[customerID][CustomerInfoEnum.lat.name]]
                vehicleObject = Vehicle(vehicleID, capacity, position, customerID,
                                        mileage=vehicle_info[VehicleInfoEnum.current_mileage.name])
                if Configs.constrains[ConstrainEnum.bin_packing]:
                    vehicleObject.set_vehicle_dimension(vehicle_info[VehicleInfoEnum.dimension.name])
                if Configs.constrains[ConstrainEnum.incompatible_item_vehicle]:
                    vehicleObject.set_compatible_items(vehicle_info[VehicleInfoEnum.compatible_item_type_list.name])
                vehicleObject.activateVehicle(volume=0)
                if leave_time > time2_go:
                    time2_go = leave_time
                vehicleObject.getCurrentRoute[0].setVehicleArriveTime(time2_go)
                vehicleObject.getCurrentRoute[0].setVehicleDepartureTime(time2_go)
                dpdp_solver.addVehicle2Pool({vehicle_info[VehicleInfoEnum.id.name]: vehicleObject})
            else:
                load_volume = 0
                requests_items_map_temp = {}
                carrying_items = vehicle_info[VehicleInfoEnum.carrying_items.name]
                request_id_on_order = []  # 存放将来生成固定线路的node顺序
                for item_id in carrying_items:
                    order_id = ongoing_items_map[item_id][ItemInfoEnum.order_id.name] + vehicleID
                    if order_id not in request_id_on_order:
                        request_id_on_order.append(order_id)
                    if order_id not in requests_items_map_temp:
                        requests_items_map_temp[order_id] = {DemandTypeEnum.delivery_only.name: []}
                    requests_items_map_temp[order_id][DemandTypeEnum.delivery_only.name].append(item_id)
                    if ongoing_items_map[item_id][
                        ItemInfoEnum.delivery_factory_id.name] not in dpdp_solver.getCustomerPool:
                        SolverInit.__gen_customer_object(dpdp_solver,
                                                         ongoing_items_map[item_id][
                                                             ItemInfoEnum.delivery_factory_id.name],
                                                         customer_id_info_map)
                    load_volume += ongoing_items_map[item_id][ItemInfoEnum.demand.name]
                new_request_id_on_order, new_requests_items_map = RequestCluster.old_requests_cluster(
                    request_id_on_order,
                    requests_items_map_temp,
                    ongoing_items_map,
                    vehicleID)
                requests_items_map.update(new_requests_items_map)
                # requests_items_map.update(requests_items_map_temp)
                arrive_time = time.strftime("%Y-%m-%d %H:%M:%S",
                                            time.localtime(vehicle_info[VehicleInfoEnum.destination.name][
                                                               DestinationInfoEnum.arrive_time.name]))
                arrive_time = datetime.strptime(arrive_time, "%Y-%m-%d %H:%M:%S")
                customerID = vehicle_info[VehicleInfoEnum.destination.name][DestinationInfoEnum.factory_id.name]
                position = [customer_id_info_map[customerID][CustomerInfoEnum.lng.name],
                            customer_id_info_map[customerID][CustomerInfoEnum.lat.name]]
                vehicleObject = Vehicle(vehicleID, capacity, position, customerID,
                                        mileage=vehicle_info[VehicleInfoEnum.current_mileage.name])
                if Configs.constrains[ConstrainEnum.bin_packing]:
                    vehicleObject.set_vehicle_dimension(vehicle_info[VehicleInfoEnum.dimension.name])
                if Configs.constrains[ConstrainEnum.incompatible_item_vehicle]:
                    vehicleObject.set_compatible_items(vehicle_info[VehicleInfoEnum.compatible_item_type_list.name])
                vehicleObject.activateVehicle(volume=load_volume)
                vehicleObject.getCurrentRoute[0].setVehicleArriveTime(arrive_time)
                vehicleObject.getCurrentRoute[0].setVehicleDepartureTime(arrive_time)
                dpdp_solver.addVehicle2Pool({vehicle_info[VehicleInfoEnum.id.name]: vehicleObject})
                dpdp_solver.getVehiclesPool[vehicleID].gen_fix_route(dpdp_solver.getCustomerPool,
                                                                     new_request_id_on_order,
                                                                     ongoing_items_map,
                                                                     requests_items_map)

        request_info["requests_items_map"].update(requests_items_map)
