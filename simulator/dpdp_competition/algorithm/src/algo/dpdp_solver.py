import json
import os
# import folium
import time
import numpy as np
from datetime import datetime, timedelta
import sys
from queue import PriorityQueue
from copy import deepcopy

from simulator.dpdp_competition.algorithm.src.common.request_pool import RequestPool
from simulator.dpdp_competition.algorithm.src.algo.constructor import SolomonInsertionHeuristic
from simulator.dpdp_competition.algorithm.src.algo.alns import AdaptiveLargeNeighborhoodSearch
from simulator.dpdp_competition.algorithm.src.utils.utlis import DateEncoder
from simulator.dpdp_competition.algorithm.conf.configs import Configs
from simulator.dpdp_competition.algorithm.src.utils.route_cost_util import route_cost
from simulator.dpdp_competition.algorithm.src.enum.request_info_enum import RequestInfoEnum
from simulator.dpdp_competition.algorithm.src.enum.demand_info_enum import DemandInfoEnum
from simulator.dpdp_competition.algorithm.src.enum.route_cost_enum import RouteCostEnum


class DPDPSolver(object):
    def __init__(self, old_request_map: dict):
        self._vehiclesPool = dict()
        self._requestsPool = RequestPool()
        self._customersPool = dict()
        self.weighted_objective = Configs.weighted_objective_function
        self.objective_score = np.infty
        self._travelCost_solver = route_cost
        self._fail_insertion_list = {}
        self._time2Go = None
        self._time_over_requests = {}
        self._old_request_map = old_request_map

    @property
    def getCustomerPool(self):
        return self._customersPool

    @property
    def getVehiclesPool(self):
        if self._time_over_requests:
            minpq_vehicle_route = self._get_minpq_vehicle_route()
            for requestID in self._time_over_requests:
                if minpq_vehicle_route.empty():
                    minpq_vehicle_route = self._get_minpq_vehicle_route()
                vehicleID = minpq_vehicle_route.get()[1]
                self._vehiclesPool[vehicleID].force_insertion(self._time_over_requests[requestID],
                                                              self._travelCost_solver)
                route = self._vehiclesPool[vehicleID].getCurrentRoute
                length = len(route)
                print(route[length-1].requestID)
        return self._vehiclesPool

    @property
    def getRequestsPool(self):
        return self._requestsPool

    def _get_minpq_vehicle_route(self):
        minpq_vehicle_route = PriorityQueue()
        for vehicleID in self._vehiclesPool:
            minpq_vehicle_route.put((len(self._vehiclesPool[vehicleID].getCurrentRoute), vehicleID))
        return minpq_vehicle_route

    def getCustomerObject(self, customerID):
        return self._customersPool[customerID]

    def getVehicleObject(self, vehicleID):
        return self._vehiclesPool[vehicleID]

    def addNewRequest2RequestsPool(self, request):
        self._requestsPool.updateUnDispatchRequest(request)

    def addVehicle2Pool(self, vehicles: dict):
        """
        :param vehicles: key: [idle, busy]
        """
        for key, value in vehicles.items():
            self._vehiclesPool[key] = value

    def push_request_bin_map_2_request_pool(self, request_bin_map: dict):
        self._requestsPool.push_request_bin_map_2_request_pool(request_bin_map)

    def updateVehiclePool(self):
        """
        更新车辆完成站点
        """
        pass

    def addCustomer2Pool(self, customers: dict):
        for key, value in customers.items():
            self._customersPool[key] = value

    def outputSolution(self):
        pass

    def _currentRouteFeasible(self, vehicleID) -> bool:
        """
        如果某辆车之前是按照原计划的线路执行
        考虑到之前站点的实际服务时间，或者实际行驶时间，
        需要检车当前状态下的solution是否是feasible
        """
        pass

    def _scheduleNormal(self, vehicleID) -> bool:
        """
        判断司机是否按照给定的顺序执行任务
        :return:
        """
        pass

    def _rearrangeRoute(self, vehicleID):
        """
        如果某辆车之前未按照计划路线执行
        需要对目前剩余的客户点重新进行一次规划
        """
        pass

    def _gen_time_out_requests_json(self, time_out_requests):
        if os.path.exists(Configs.time_out_requests):
            with open(Configs.time_out_requests, "r") as f:
                time_out_requests_old = json.load(f)
            for requestID in time_out_requests:
                if requestID in self._old_request_map:
                    for old_request_id in self._old_request_map[requestID]:
                        request_id_temp = old_request_id
                        if "-" in old_request_id:
                            index_ = old_request_id.index("-")
                            request_id_temp = old_request_id[:index_]
                        time_out_requests_old[request_id_temp] = time_out_requests[requestID]
                        time_out_requests_old[request_id_temp][RequestInfoEnum.requestID.name] = request_id_temp
                else:
                    time_out_requests_old[requestID] = time_out_requests[requestID]
            with open(Configs.time_out_requests, "w") as f:
                json.dump(time_out_requests_old, f, cls=DateEncoder, indent=4)
        else:
            time_out_requests_old = {}
            for requestID in time_out_requests:
                if requestID in self._old_request_map:
                    for old_request_id in self._old_request_map[requestID]:
                        request_id_temp = old_request_id
                        if "-" in old_request_id:
                            index_ = old_request_id.index("-")
                            request_id_temp = old_request_id[:index_]
                        time_out_requests_old[request_id_temp] = time_out_requests[requestID]
                        time_out_requests_old[request_id_temp][RequestInfoEnum.requestID.name] = request_id_temp
                else:
                    time_out_requests_old[requestID] = time_out_requests[requestID]
            with open(Configs.time_out_requests, "w") as f:
                json.dump(time_out_requests_old, f, cls=DateEncoder, indent=4)

    def _insertion_idle_vehicle(self):
        minpq_vehicle_route = self._get_minpq_vehicle_route()
        null_vehicles = set()
        while not minpq_vehicle_route.empty():
            (length, vehicleID) = minpq_vehicle_route.get()
            if length == 1:
                null_vehicles.add(vehicleID)
            else:
                break
        for requests_info in self._fail_insertion_list:
            for requestID in requests_info:
                tw_left = datetime.strptime(requests_info[requestID][RequestInfoEnum.pickup_demand_info.name][DemandInfoEnum.time_window.name][0],
                                             "%Y-%m-%d %H:%M:%S")
                tw_right = tw_left + timedelta(hours=4)
                if tw_right + timedelta(minutes=120) < self._time2Go:
                    self._time_over_requests[requestID] = requests_info[requestID]
                if null_vehicles:
                    earliest_finish_time = datetime.strptime(
                        requests_info[requestID][RequestInfoEnum.pickup_demand_info.name][DemandInfoEnum.time_window.name][1],
                        "%Y-%m-%d %H:%M:%S") + timedelta(hours=100)
                    best_insertion_vehicle = None
                    for vehicleID in null_vehicles:
                        route = self._vehiclesPool[vehicleID].getCurrentRoute
                        vehicle_leave_time = route[0].vehicleDepartureTime
                        travel_cost1 = self._travelCost_solver.getTravelCost(route[0].customerID,
                                                                             requests_info[requestID][
                                                                                 RequestInfoEnum.pickup_demand_info.name][DemandInfoEnum.customer_id.name])
                        travel_cost2 = self._travelCost_solver.getTravelCost(
                            requests_info[requestID][RequestInfoEnum.pickup_demand_info.name][DemandInfoEnum.customer_id.name],
                            requests_info[requestID][RequestInfoEnum.delivery_demand_info.name][DemandInfoEnum.customer_id.name])
                        request_finish_time = vehicle_leave_time + timedelta(seconds=travel_cost1[RouteCostEnum.travel_time.name] +
                                                                                     travel_cost2[RouteCostEnum.travel_time.name])
                        if request_finish_time < earliest_finish_time:
                            earliest_finish_time = request_finish_time
                            best_insertion_vehicle = vehicleID
                    if requestID in self._time_over_requests:
                        self._time_over_requests.pop(requestID)
                    self._requestsPool.updateDispatchedRequestPool(requests_info[requestID]["requestID"], "add")
                    self._vehiclesPool[best_insertion_vehicle].force_insertion(requests_info[requestID],
                                                                               self._customersPool)
                    null_vehicles.remove(best_insertion_vehicle)

    def constructEngine(self,
                        time2Go=datetime.strptime(Configs.date + " 0:0:0", "%Y-%m-%d %H:%M:%S"),
                        CPU_limit=10.):
        """
        所有requests都要得到分配，并且所有route要满足时间窗，载重等约束条件
        """
        # TODO 需要完善如果插入失败后的预备方案
        self._time2Go = time2Go
        start_time = time.time()
        for vehicleID in self._vehiclesPool:
            if not self._scheduleNormal(vehicleID) or not self._currentRouteFeasible(vehicleID):
                self._rearrangeRoute(vehicleID)

        constructor = SolomonInsertionHeuristic(self._vehiclesPool,
                                                self._requestsPool,
                                                self._customersPool)
        if constructor.solve(time2Go=time2Go, CPU_limit=CPU_limit):
            self._vehiclesPool, self._customersPool, self._requestsPool = constructor.outputSolution
            for customerID in self._customersPool:
                self._customersPool[customerID].gen_node_port_map()
            self._gen_object_score()
            self._print_solution()
        else:
            self._vehiclesPool, self._customersPool, self._requestsPool = constructor.outputSolution
            fail_insertion_requests = constructor.get_fail_insertion_requests
            self._fail_insertion_list = deepcopy(fail_insertion_requests)
            time_out_requests = {}
            if fail_insertion_requests:
                for requests_info in fail_insertion_requests:
                    requests_info_temp = requests_info
                    for requestID in requests_info:
                        tw_right = datetime.strptime(requests_info_temp[requestID][RequestInfoEnum.pickup_demand_info.name][DemandInfoEnum.time_window.name][1],
                                                     "%Y-%m-%d %H:%M:%S")
                        if len(self._vehiclesPool) == 100:
                            tw_right += timedelta(hours=2)
                        else:
                            tw_right += timedelta(hours=1)
                        requests_info_temp[requestID][RequestInfoEnum.pickup_demand_info.name][DemandInfoEnum.time_window.name][1] = str(tw_right)
                        requests_info_temp[requestID][RequestInfoEnum.delivery_demand_info.name][DemandInfoEnum.time_window.name][1] = str(tw_right)
                        requestID_temp = requestID
                        if "-" in requestID:
                            _index = requestID.index("-")
                            requestID_temp = requestID[:_index]
                        time_out_requests[requestID_temp] = requests_info_temp[requestID]
                        self.addNewRequest2RequestsPool(requests_info_temp)
                self._gen_time_out_requests_json(deepcopy(time_out_requests))
            time_now = time.time()
            if time_now - start_time < 7 * 60:
                self.heuristicEngine(CPU_limit=1, mission="repair")
            else:
                self._gen_object_score()
                self._insertion_idle_vehicle()
            self._print_solution()

    def heuristicEngine(self, time2Go=datetime.strptime(Configs.date + " 0:0:0", "%Y-%m-%d %H:%M:%S"),
                        CPU_limit=10,
                        mission="improvement"):
        heuristicSolver = AdaptiveLargeNeighborhoodSearch(self._vehiclesPool,
                                                          self._requestsPool,
                                                          self._customersPool,
                                                          self.objective_score,
                                                          time2Go=time2Go,
                                                          mission=mission)
        heuristicSolver.solve(CPU_limit)
        solution = heuristicSolver.outputSolution
        if solution["score"] != np.infty:
            self._vehiclesPool = solution["source_pool"].vehicles
            self._requestsPool = solution["source_pool"].requests
            self._customersPool = solution["source_pool"].customers
            self._fail_insertion_list = {}
        else:
            self._insertion_idle_vehicle()
        self._gen_object_score()

    def _print_solution(self):
        objective_score = 0
        score_temp = 0
        for vehicleID in self._vehiclesPool:
            if len(self._vehiclesPool[vehicleID].getCurrentRoute) > 1:
                self._vehiclesPool[vehicleID].updateTravelCost()
                objective_score += self._vehiclesPool[vehicleID].getCurrentRouteCost
                for index, node in enumerate(self._vehiclesPool[vehicleID].getCurrentRoute):
                    if index == 0:
                        # logger.info(f"vehicle_id: {vehicleID}, "
                        #             f"request_id: {node.requestID}, "
                        #             f"demand_type: {node.demandType}, "
                        #             f"customer_id:{node.customerID}, "
                        #             f"arrive_time: {node.vehicleArriveTime}, "
                        #             f"leave_time: {node.vehicleDepartureTime}")
                        print(" vehicle_id: ", vehicleID,
                              " request_id: ", node.requestID,
                              " demand_type: ", node.demandType,
                              " customer_id: ", node.customerID,
                              " arrive_time: ", node.vehicleArriveTime,
                              " leave_time: ", node.vehicleDepartureTime, file=sys.stderr)

                    else:
                        dis = self._travelCost_solver.getTravelCost(
                            self._vehiclesPool[
                                vehicleID].getCurrentRoute[
                                index - 1].customerID,
                            node.customerID)
                        score_temp += dis["distance"]
                        print(" vehicle_id: ", vehicleID,
                              " request_id: ", node.requestID,
                              " demand_type:  ", node.demandType,
                              " customer_id: ", node.customerID,
                              " arrive_time:", node.vehicleArriveTime,
                              " leave_time:", node.vehicleDepartureTime,
                              " duration: ", dis["travel_time"] / 60.,
                              " current_mileage: ", dis["distance"], file=sys.stderr)
                        # duration = dis["travel_time"]
                        # distance = dis["distance"]
                        # logger.info(f"vehicle_id: {vehicleID}, "
                        #             f"request_id: {node.requestID}, "
                        #             f"demand_type: {node.demandType}, "
                        #             f"customer_id:{node.customerID}, "
                        #             f"arrive_time: {node.vehicleArriveTime}, "
                        #             f"leave_time: {node.vehicleDepartureTime}, "
                        #             f"duration(seconds): {duration}")

    def _gen_object_score(self):
        self.objective_score = 0
        for vehicleID in self._vehiclesPool:
            if len(self._vehiclesPool[vehicleID].getCurrentRoute) > 1:
                self._vehiclesPool[vehicleID].updateTravelCost()
                self.objective_score += self._vehiclesPool[vehicleID].getCurrentRouteCost
                self.objective_score += self._vehiclesPool[vehicleID].getMileage

    def foliumPlot(self, customer_id_info_map):
        # vehicle_node_map = dict()
        # city_map = folium.Map(location=[39.93, 116.40], zoom_start=10)
        # for vehicleID in self._vehiclesPool:
        #     if len(self._vehiclesPool[vehicleID].getCurrentRoute) > 1:
        #         temp = []
        #         for node in self._vehiclesPool[vehicleID].getCurrentRoute:
        #             cs = customer_id_info_map[node.customerID]
        #             temp.append([cs["lat"], cs["lng"]])
        #         vehicle_node_map[vehicleID] = temp
        #         folium.PolyLine(temp, color='black').add_to(city_map)
        # city_map.save("route.html")
        # wb.open("route.html")
        # print(vehicle_node_map)
        pass


if __name__ == "__main__":
    pass
