import time
from typing import Dict
import numpy as np
from copy import deepcopy
import math
from datetime import datetime, timedelta
import sys

from simulator.dpdp_competition.algorithm.src.vehicle import vehicle
from simulator.dpdp_competition.algorithm.src.customer import customer
from simulator.dpdp_competition.algorithm.src.requestPool import requestPool
from simulator.dpdp_competition.algorithm.src.Operator import ShawRemovalOperator, RandomRemovalOperator, WorstRemovalOperator, GreedyInsertionOperator, \
    RegretInsertionOperator
from simulator.dpdp_competition.algorithm.src.travelCost import costDatabase
from simulator.dpdp_competition.algorithm.src.utlis import checker, feasibleRearrangePortAssignmentSchedule, sourcePool

import simulator.dpdp_competition.algorithm.src.getConfig

gConfig = simulator.dpdp_competition.algorithm.src.getConfig.get_config()


class AdaptiveLargeNeighborhoodSearch(object):
    # ref: Ropke, Pisinge 2006 - TS
    def __init__(self,
                 vehicles: Dict[str, vehicle],
                 requests: requestPool,
                 customers: Dict[str, customer],
                 objective_score: float,
                 travelCost_solver: costDatabase,
                 time2Go,
                 start_time = time.time()):
        self._source_pool = deepcopy(sourcePool(vehicles, customers, requests))
        self._customers = self._source_pool.customers
        self._requests = self._source_pool.requests
        self._vehicles = self._source_pool.vehicles
        self._travelCost_solver = travelCost_solver
        self._bestSolution = {"score": objective_score,
                              "source_pool": deepcopy(self._source_pool)}
        self._currentSolution = {"score": objective_score,
                                 "source_pool": deepcopy(self._source_pool)}
        self._start_time = start_time
        self.removeOperator = dict()
        self.repairOperator = dict()
        self._destroyOperator_paras = {"shaw": {"weight": 1, "score": 0, "trials": 0},
                                       "random": {"weight": 1, "score": 0, "trials": 0},
                                       "worst": {"weight": 1, "score": 0, "trials": 0}}
        self._repairOperator_paras = {"greedy": {"weight": 1, "score": 0, "trials": 0},
                                      "regret": {"weight": 1, "score": 0, "trials": 0}}
        self._time_2_go = time2Go
        customers_temp = set()
        for vehicleID in self._vehicles:
            length = len(self._vehicles[vehicleID].getCurrentRoute)
            if length > 1:
                for index, node in enumerate(self._vehicles[vehicleID].getCurrentRoute):
                    if index > 0:
                        customer_object = self._customers[node.customerID]
                        customer_object.getDispatchedRequestSet[node.requestID] = node
                        if node.customerID not in customers_temp:
                            customers_temp.add(node.customerID)
                        if node.requestID in customer_object.get_node_port_map:
                            port_index = customer_object.get_node_port_map[node.requestID]
                            customer_object.getCurrentPortStatus[port_index[0]][port_index[1]] = node
        # 为SA选定合适的参数
        # TODO (死参数,后续需要近一步 tuning)初始温度选择的原则，是比初始解差5%的解被接受的概率为50%。
        self._SA_cool_rate = gConfig["sa_cool_rate"]
        self._SA_temperature = -0.05 * objective_score / math.log(0.4)
        # print(self._SA_temperature)

    @staticmethod
    def _chooseOperator(operator_paras):
        weights = dict()
        total_weight = 0
        for item in operator_paras:
            weights[item] = operator_paras[item]["weight"]
            total_weight += operator_paras[item]["weight"]
        weights = sorted(weights.items(), key=lambda x: x[1])
        rand_value = np.random.randint(total_weight)
        temp = 0
        for destroy_weight_pair in weights:
            temp += destroy_weight_pair[1]
            if rand_value < temp:
                return destroy_weight_pair[0]

    def _removals(self, removals):
        removal_vehicleIDs = set()
        active_nodes = set()
        for pickup_node in removals:
            # 删除路径中的pickup_node 以及delivery_node, 并且要修改node的左右孩子
            assert pickup_node in self._vehicles[removals[pickup_node]].getCurrentRoute
            pickup_node_index = self._vehicles[removals[pickup_node]].getCurrentRoute.index(pickup_node)

            # update customers
            temp = True
            if pickup_node.leftNode.demandType != "depot" and pickup_node.leftNode.customerID == pickup_node.customerID \
                     and pickup_node.leftNode not in removals:
                active_nodes.add(pickup_node.leftNode)
                temp = False
            if pickup_node.rightNode.customerID == pickup_node.customerID and temp \
                    and pickup_node.rightNode not in removals:
                active_nodes.add(pickup_node.rightNode)

            if pickup_node.requestID in self._customers[pickup_node.customerID].get_node_port_map:
                p_port_index = self._customers[pickup_node.customerID].get_node_port_map[pickup_node.requestID]
                self._customers[pickup_node.customerID].deleteNodeFromPort(p_port_index[0], p_port_index[1])

            if pickup_node.brotherNode.requestID in self._customers[pickup_node.brotherNode.customerID].get_node_port_map:
                d_port_index = self._customers[pickup_node.brotherNode.customerID].get_node_port_map[pickup_node.brotherNode.requestID]
                self._customers[pickup_node.brotherNode.customerID].deleteNodeFromPort(d_port_index[0], d_port_index[1])
            self._customers[pickup_node.customerID].removeRequest(pickup_node.requestID)
            self._customers[pickup_node.brotherNode.customerID].removeRequest(pickup_node.brotherNode.requestID)

            # update vehicles
            self._vehicles[removals[pickup_node]].deleteNodeFromRoute(pickup_node_index)
            # update requests
            self._requests.updateUnDispatchRequest(
                {pickup_node.requestID: self._requests.getDispatchedPool[pickup_node.requestID]},
                "add")
            self._requests.updateDispatchedRequestPool(pickup_node.requestID, "remove")

            removal_vehicleIDs.add(removals[pickup_node])

        # TODO 原则上找到要移除的pickup点，并修改其后续node的到达时间，或离开时间（当移除同一批次的点时，会改变其离开时间）
        # 修改vehicleArriveTime

        vehicles_temp = set()
        for vehicleID in removal_vehicleIDs:
            if len(self._vehicles[vehicleID].getCurrentRoute) > 1:
                n = len(self._vehicles[vehicleID].getCurrentRoute)
                route = self._vehicles[vehicleID].getCurrentRoute
                for i in range(n - 1):
                    init_arrive_time = route[i + 1].vehicleArriveTime
                    new_arrive_time = route[i].vehicleDepartureTime + \
                                      timedelta(seconds=self._travelCost_solver.getTravelCost(route[i].customerID,
                                                                                              route[i + 1].customerID)[
                                                                                                        "travel_time"])
                    new_departure_time = new_arrive_time + timedelta(seconds=route[i+1].processTime)
                    if route[i+1].customerID != route[i].customerID:
                        new_departure_time += timedelta(seconds=gConfig["static_process_time_on_customer"])
                    if init_arrive_time != new_arrive_time:
                        route[i+1].setVehicleArriveTime(new_arrive_time)
                        route[i+1].setVehicleDepartureTime(new_departure_time)
                        if vehicleID not in vehicles_temp:
                            active_nodes.add(route[i + 1])
                            vehicles_temp.add(vehicleID)
            else:
                continue

        for vehicleID in self._vehicles:
            length = len(self._vehicles[vehicleID].getCurrentRoute)
            if length > 1:
                for index, node in enumerate(self._vehicles[vehicleID].getCurrentRoute):
                    if index > 0:
                        customer_object = self._customers[node.customerID]
                        customer_object.getDispatchedRequestSet[node.requestID] = node
                        if node.requestID in customer_object.get_node_port_map:
                            port_index = customer_object.get_node_port_map[node.requestID]
                            customer_object.getCurrentPortStatus[port_index[0]][port_index[1]] = node
        for node in active_nodes:
            if node in self._vehicles[node.vehicleID].getCurrentRoute:
                flag = feasibleRearrangePortAssignmentSchedule(self._customers, node.customerID, node, tp="destroy")
                if not flag:
                    # print("ALNS destroy process fail!!!!!!!!!")
                    return False
                else:
                    for customerID in self._customers:
                        if self._customers[customerID].getDispatchedRequestSet:
                            for requestID in self._customers[customerID].getDispatchedRequestSet:
                                node_temp = self._customers[customerID].getDispatchedRequestSet[requestID]
                                assert node_temp in self._vehicles[node_temp.vehicleID].getCurrentRoute
                    continue
        return True

    def _destroy(self):
        min_remove_number = gConfig["alns_min_request_remove_number"]
        epsilon = gConfig["alns_request_remove_number_coff"]
        total_requests = len(self._requests.getDispatchedPool)
        max_remove_number = math.ceil(
            min(gConfig["alns_request_remove_number_upperbound"], epsilon * total_requests)) + 1
        # TODO 此处可能有些问题
        if min_remove_number < max_remove_number:
            removeRequest_number = np.random.randint(min_remove_number, max_remove_number)
        else:
            removeRequest_number = min_remove_number
        if removeRequest_number > total_requests:
            removeRequest_number = total_requests
        # print(removeRequest_number)
        # destroyID = self._chooseOperator(self._destroyOperator_paras)
        destroyID = "random"
        if destroyID == "shaw":
            self.removeOperator = {"engine": ShawRemovalOperator(self._vehicles),
                                   "engineID": "shaw"}
            self._destroyOperator_paras["shaw"]["trials"] += 1
        elif destroyID == "random":
            self.removeOperator = {"engine": RandomRemovalOperator(self._vehicles),
                                   "engineID": "random"}
            self._destroyOperator_paras["random"]["trials"] += 1
        else:
            self.removeOperator = {"engine": WorstRemovalOperator(self._vehicles),
                                   "engineID": "worst"}
            self._destroyOperator_paras["worst"]["trials"] += 1
        removals = self.removeOperator["engine"].remove(removeRequest_number)
        # print("destroyID is: ", self.removeOperator["engineID"])
        return self._removals(removals)

    def _repair(self):
        repairID = self._chooseOperator(self._repairOperator_paras)
        repairID = "greedy"
        if repairID == "greedy":
            self.repairOperator = {"engine": GreedyInsertionOperator(self._vehicles,
                                                                     self._requests,
                                                                     self._customers,
                                                                     self._travelCost_solver),
                                   "engineID": "greedy"}
            self._repairOperator_paras["greedy"]["trials"] += 1
        else:
            self.repairOperator = {"engine": RegretInsertionOperator(self._vehicles,
                                                                     self._requests,
                                                                     self._customers,
                                                                     self._travelCost_solver),
                                   "engineID": "regret"}
            self._repairOperator_paras["regret"]["trials"] += 1
        # print("repairID is: ", self.repairOperator["engineID"])
        flag = self.repairOperator["engine"].insert(time2Go=self._time_2_go, tp="heuristic")
        # assert flag == True
        if not flag:
            # print("执行失败的算子是: ", self.repairOperator["engineID"])
            pass
        return flag

    def _resetOperatorsParas(self):
        # weight 更新， score, trials清零
        for item in self._destroyOperator_paras:
            if self._destroyOperator_paras[item]["trials"] > 0:
                r = gConfig["alns_reaction_parameter"]
                current_weight = self._destroyOperator_paras[item]["weight"]
                current_score = self._destroyOperator_paras[item]["score"]
                current_trials = self._destroyOperator_paras[item]["trials"]
                self._destroyOperator_paras[item]["weight"] = current_weight * (1 - r) + r * (
                        current_score / current_trials)
                self._destroyOperator_paras[item]["score"] = 0
                self._destroyOperator_paras[item]["trials"] = 0

        for item in self._repairOperator_paras:
            if self._repairOperator_paras[item]["trials"] > 0:
                r = gConfig["alns_reaction_parameter"]
                current_weight = self._repairOperator_paras[item]["weight"]
                current_score = self._repairOperator_paras[item]["score"]
                current_trials = self._repairOperator_paras[item]["trials"]
                self._repairOperator_paras[item]["weight"] = current_weight * (1 - r) + r * (
                        current_score / current_trials)
                self._repairOperator_paras[item]["score"] = 0
                self._repairOperator_paras[item]["trials"] = 0
        # print(self._repairOperator_paras)
        # print(self._destroyOperator_paras)

    def _updateOperatorScore(self, score):
        destroyID = self.removeOperator["engineID"]
        repairID = self.repairOperator["engineID"]
        self._repairOperator_paras[repairID]["score"] += score
        self._destroyOperator_paras[destroyID]["score"] += score

    def _SA_accept(self) -> bool:
        temp_score = self.repairOperator["engine"].getObjectiveScore
        # print("待决策方案的score: ", temp_score)
        if temp_score < self._currentSolution["score"]:
            return True
        else:
            if np.random.rand() < np.exp((self._currentSolution["score"] - temp_score) / self._SA_temperature):
                return True
            else:
                return False

    def solve(self, CPU_limit=10):
        total_iteration_count = 0
        none_improve_iteration_count = 0
        last_current_score = None
        source_pool_init = deepcopy(self._source_pool)
        # print("init score is:", self._bestSolution["score"], file=sys.stderr)
        while time.time() - self._start_time < CPU_limit * 60:
            # print("iter:", total_iteration_count, "--------------------------------------")
            if total_iteration_count % gConfig["alns_segment_size"] == 0:
                self._resetOperatorsParas()

            if not self._destroy():
                current_source_pool = deepcopy(self._currentSolution["source_pool"])
                self._vehicles = current_source_pool.vehicles
                self._customers = current_source_pool.customers
                self._requests = current_source_pool.requests
                continue
            if self._repair():
                if self._SA_accept():
                    self._vehicles, self._customers, self._requests = self.repairOperator["engine"].outputSolution()
                    for customerID in self._customers:
                        self._customers[customerID].gen_node_port_map()
                    # checker(self._vehicles)
                    score = self.repairOperator["engine"].getObjectiveScore
                    self._currentSolution = {"score": score,
                                             "source_pool": deepcopy(sourcePool(self._vehicles,
                                                                                self._customers,
                                                                                self._requests))}

                    if score < self._bestSolution["score"]:
                        self._updateOperatorScore(gConfig["alns_found_best"])
                        self._bestSolution = {"score": score,
                                              "source_pool": deepcopy(sourcePool(self._vehicles,
                                                                                 self._customers,
                                                                                 self._requests))}
                    else:
                        self._updateOperatorScore(gConfig["alns_better_than_current"])
                else:
                    self._updateOperatorScore(gConfig["alns_worst_than_current"])
            else:
                # print("修复算法执行失败")
                pass
            current_source_pool = deepcopy(self._currentSolution["source_pool"])
            self._vehicles = current_source_pool.vehicles
            self._customers = current_source_pool.customers
            self._requests = current_source_pool.requests
            total_iteration_count += 1
            self._SA_temperature /= self._SA_cool_rate

            if self._currentSolution["score"] != last_current_score:
                none_improve_iteration_count = 0
                last_current_score = self._currentSolution["score"]
            else:
                none_improve_iteration_count += 1
            if none_improve_iteration_count > gConfig["alns_none_improve_iteration"]:
                none_improve_iteration_count = 0
                # print("--------------------------------------------------------------------------------------------")
                # print("重新开始")
                source_pool_temp = deepcopy(source_pool_init)
                self._vehicles = source_pool_temp.vehicles
                self._customers = source_pool_temp.customers
                self._requests = source_pool_temp.requests
            #
            # print("iteration is: ", total_iteration_count,
            #       " best score: ", self._bestSolution["score"],
            #       " current score: ", self._currentSolution["score"])
        # print("ALNS score is:", self._bestSolution["score"], file=sys.stderr)
    @property
    def outputSolution(self):
        return self._bestSolution


if __name__ == "__main__":
    # print(math.exp(-1))
    pass
