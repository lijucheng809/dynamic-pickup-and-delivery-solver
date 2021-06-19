import folium
import numpy as np
import webbrowser as wb
from datetime import datetime, timedelta
import sys

from simulator.dpdp_competition.algorithm.src.requestPool import requestPool
from simulator.dpdp_competition.algorithm.src.constructor import solomonInsertionHeuristic
from simulator.dpdp_competition.algorithm.src.travelCost import costDatabase
from simulator.dpdp_competition.algorithm.src.Operator import ShawRemovalOperator, RandomRemovalOperator, WorstRemovalOperator
from simulator.dpdp_competition.algorithm.src.ALNS import AdaptiveLargeNeighborhoodSearch
from simulator.dpdp_competition.algorithm.src.utlis import checker

import simulator.dpdp_competition.algorithm.src.getConfig
gConfig = simulator.dpdp_competition.algorithm.src.getConfig.get_config()


class DVRPPD_Solver(object):
    def __init__(self):
        self._vehiclesPool = dict()
        self._requestsPool = requestPool()
        self._customersPool = dict()
        self.weighted_objective = gConfig["weighted_objective_function"]
        self.objective_score = np.infty
        self._travelCost_solver = costDatabase()

    @property
    def getCustomerPool(self):
        return self._customersPool

    @property
    def getVehiclesPool(self):
        return self._vehiclesPool

    @property
    def getRequestsPool(self):
        return self._requestsPool

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

    def constructEngine(self, time2Go=datetime.strptime(gConfig["date"] + " 0:0:0", "%Y-%m-%d %H:%M:%S")):
        """
        所有requests都要得到分配，并且所有route要满足时间窗，载重等约束条件
        """
        # TODO 需要完善如果插入失败后的预备方案
        for vehicleID in self._vehiclesPool:
            if not self._scheduleNormal(vehicleID) or not self._currentRouteFeasible(vehicleID):
                self._rearrangeRoute(vehicleID)

        constructor = solomonInsertionHeuristic(self._vehiclesPool,
                                                self._requestsPool,
                                                self._customersPool,
                                                self._travelCost_solver)
        if constructor.solve(time2Go=time2Go):
            self._vehiclesPool, self._customersPool, self._requestsPool = constructor.outputSolution
            for customerID in self._customersPool:
                self._customersPool[customerID].gen_node_port_map()
            self._gen_object_score()
            self._print_solution()
            # checker(self._vehiclesPool)
            return True
        else:
            self._vehiclesPool, self._customersPool, self._requestsPool = constructor.outputSolution
            fail_insertion_requests = constructor.get_fail_insertion_requests
            if fail_insertion_requests:
                for requests_info in fail_insertion_requests:
                    self.addNewRequest2RequestsPool(requests_info)
            self.heuristicEngine(CPU_limit=2)
            constructor = solomonInsertionHeuristic(self._vehiclesPool,
                                                    self._requestsPool,
                                                    self._customersPool,
                                                    self._travelCost_solver)
            if constructor.solve():
                return True
            else:
                # fail_insertion_requests，存到本地
                # 等下一个时间点，再尝试进行插入
                # 12：00 fail, 12:10 fail, 12:20,fail， 但是呢，这个订单是在12:04创建，超过30分种都没插入成功的话，这个时候就需要
                # 强行插入了，【12：04, 16:04】 , 16:10完成， 【12：04， 16：10】
                # return True
                pass
        return False

    def heuristicEngine(self, time2Go=datetime.strptime(gConfig["date"] + " 0:0:0", "%Y-%m-%d %H:%M:%S"), CPU_limit=10):
        heuristicSolver = AdaptiveLargeNeighborhoodSearch(self._vehiclesPool,
                                                          self._requestsPool,
                                                          self._customersPool,
                                                          self.objective_score,
                                                          self._travelCost_solver,
                                                          time2Go=time2Go)
        heuristicSolver.solve(CPU_limit)
        solution = heuristicSolver.outputSolution
        self._vehiclesPool = solution["source_pool"].vehicles
        self._requestsPool = solution["source_pool"].requests
        self._customersPool = solution["source_pool"].customers

    def _print_solution(self):
        objective_score = 0
        score_temp = 0
        for vehicleID in self._vehiclesPool:
            if len(self._vehiclesPool[vehicleID].getCurrentRoute) > 1:
                self._vehiclesPool[vehicleID].updateTravelCost(self._travelCost_solver)
                objective_score += self._vehiclesPool[vehicleID].getCurrentRouteCost
                for index, node in enumerate(self._vehiclesPool[vehicleID].getCurrentRoute):
                    if index == 0:
                        print("vehicleID: ", vehicleID,
                              "requestID: ", node.requestID,
                              "demandType:  ", node.demandType,
                              "customerID: ", node.customerID,
                              "     arrive_time:", node.vehicleArriveTime,
                              "leave_time:", node.vehicleDepartureTime, file=sys.stderr)
                    else:
                        dis = self._travelCost_solver.getTravelCost(
                            self._vehiclesPool[
                                vehicleID].getCurrentRoute[
                                index - 1].customerID,
                            node.customerID)
                        score_temp += dis["distance"]
                        print("vehicleID: ", vehicleID,
                              "requestID: ", node.requestID,
                              "demandType:  ", node.demandType,
                              "customerID: ", node.customerID,
                              "     arrive_time:", node.vehicleArriveTime,
                              "leave_time:", node.vehicleDepartureTime,
                              "travel_time: ", dis["travel_time"] / 60.,
                              "dis: ", dis["distance"], file=sys.stderr)
        # print("score is:", objective_score)
        # for customerID in self._customersPool:
        #     ports = self._customersPool[customerID].getCurrentPortStatus
        #     for index, port in enumerate(ports):
        #         if len(port) > 0:
        #             print("customerID is:", customerID,
        #                   "port ID is:", index,
        #                   end=" ")
        #             for node in port:
        #                 print("[vehicleID is:", node.vehicleID,
        #                       "requestID is ", node.requestID,
        #                       "   arrive_time is:", node.vehicleArriveTime,
        #                       "leave_time is:", node.vehicleDepartureTime, "]",
        #                       end=" ")
        #             print()

    def _gen_object_score(self):
        self.objective_score = 0
        for vehicleID in self._vehiclesPool:
            if len(self._vehiclesPool[vehicleID].getCurrentRoute) > 1:
                self._vehiclesPool[vehicleID].updateTravelCost(self._travelCost_solver)
                self.objective_score += self._vehiclesPool[vehicleID].getCurrentRouteCost


    def foliumPlot(self, customer_id_info_map):
        vehicle_node_map = dict()
        city_map = folium.Map(location=[39.93, 116.40], zoom_start=10)
        for vehicleID in self._vehiclesPool:
            if len(self._vehiclesPool[vehicleID].getCurrentRoute) > 1:
                temp = []
                for node in self._vehiclesPool[vehicleID].getCurrentRoute:
                    cs = customer_id_info_map[node.customerID]
                    temp.append([cs["lat"], cs["lng"]])
                vehicle_node_map[vehicleID] = temp
                folium.PolyLine(temp, color='black').add_to(city_map)
        city_map.save("route.html")
        wb.open("route.html")
        # print(vehicle_node_map)


if __name__ == "__main__":
    pass
