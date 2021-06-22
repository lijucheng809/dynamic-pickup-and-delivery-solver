from typing import List, Dict
from datetime import datetime, timedelta
from queue import PriorityQueue

from simulator.dpdp_competition.algorithm.src.travelCost import costDatabase
from simulator.dpdp_competition.algorithm.src.utlis import customer_request_combination
import simulator.dpdp_competition.algorithm.src.getConfig
gConfig = simulator.dpdp_competition.algorithm.src.getConfig.get_config()


class customer(object):
    def __init__(self,
                 position,
                 customerID,
                 port_num=6):
        """
        :param position: [lng, lat]
        :param customerID: "str or int"
        :param port_num: 可供停靠的卡位数
        """
        self._customerID = customerID
        self._position = position
        self._port_num = port_num
        self._dispatchedRequests = dict()  # 已分配分配卡位的需求
        self._port_reserveTable = [[] for i in range(self._port_num)]
        self._unfinished_demand_info = dict()
        self._finish_demand_info = dict()  # 可存于数据库，用于后续数据分析
        self._node_port_map = dict()


    @property
    def getDispatchedRequestSet(self):
        return self._dispatchedRequests

    @property
    def getUnfinishedDemands(self):
        return self._unfinished_demand_info

    @property
    def getPosition(self):
        return self._position

    @property
    def getCurrentPortStatus(self):
        return self._port_reserveTable

    @property
    def get_node_port_map(self):
        return self._node_port_map

    def clearPortReserveTable(self):
        self._port_reserveTable = [[] for i in range(self._port_num)]

    def deleteNodeFromPort(self, portID, queueNum):
        node = self._port_reserveTable[portID][queueNum]
        assert node.requestID in self._node_port_map

        tip = True
        if node.leftNode.demandType != "depot" and node.leftNode.customerID == node.customerID:
            tip = False
            self._port_reserveTable[portID][queueNum] = node.leftNode
            self._node_port_map.pop(node.requestID)
            self._node_port_map[node.leftNode.requestID] = (portID, queueNum)

        if tip and node.rightNode and node.rightNode.customerID == node.customerID:
            tip = False
            # print(node.requestID, self._port_reserveTable[portID][queueNum].requestID)
            self._port_reserveTable[portID][queueNum] = node.rightNode
            self._node_port_map.pop(node.requestID)
            self._node_port_map[node.rightNode.requestID] = (portID, queueNum)
        if tip:
            del self._port_reserveTable[portID][queueNum]
            self.gen_node_port_map()

    def gen_node_port_map(self):
        self._node_port_map.clear()
        for i in range(self._port_num):
            if len(self._port_reserveTable[i]) > 0:
                for index, node in enumerate(self._port_reserveTable[i]):
                    self._node_port_map[node.requestID] = (i, index)
            else:
                continue

    def getTravelCost(self,
                      anotherCustomerPosition: List[float],
                      inquireTime=datetime.now()):
        """
        :param anotherCustomerPosition:
        :param inquireTime:
        :return: {"distance": float, "travel_time": minutes}
        """
        pass

    def getEarliestDockingTime(self, processTime):
        """
        获取最早可以停靠的时间
        :param processTime: 装卸车所需要的硬性时间（包括进厂办手续时间，实际装卸车所需时间）
        :return: {"portNum": portNum, "beginDockingTime": time}
        """
        pass

    @staticmethod
    def _getRightNode(node, batch_node):
        right_node = None
        if batch_node:
            if node.rightNode:
                if node.rightNode.customerID == node.customerID:
                    right_node, temp_node = node.rightNode, node
                    while right_node and right_node.customerID == temp_node.customerID:
                        right_node, temp_node = right_node.rightNode, right_node
                else:
                    right_node = node.rightNode
        else:
            if node.rightNode:
                right_node = node.rightNode

        return right_node

    def rearrangeReservedPort(self, tp, travelCost_solver=costDatabase()):
        """
        当有新的装卸需求插入时，可能会打乱当前卡位的分配方案，需要对车辆进行重新分配卡位，按照先到先服务原则
        :return:
        """
        q_unDispatchedNode = PriorityQueue()
        q_dispatchedNode = PriorityQueue()
        nodeList = []
        self.clearPortReserveTable()
        # 找到在该站点同一车次的订单
        batchNode = {}
        temp_nodes = set()
        key = 1
        tip = False
        for requestID, node in self._dispatchedRequests.items():
            if node not in temp_nodes:
                q_unDispatchedNode.put((node.vehicleArriveTime, node))
                if node.leftNode and node.leftNode.requestID != node.requestID and node.leftNode.requestID in self._dispatchedRequests or \
                        node.rightNode and node.rightNode.requestID != node.requestID and node.rightNode.requestID in self._dispatchedRequests:
                    batchNode[key] = set()
                    batchNode[key].add(node)
                    temp_nodes.add(node)
                    left_node, right_node = node.leftNode, node.rightNode
                    node_temp1, node_temp2 = node, node
                    while left_node.demandType != "depot" and left_node.customerID == node_temp1.customerID:
                        batchNode[key].add(left_node)
                        temp_nodes.add(left_node)
                        left_node, node_temp1 = left_node.leftNode, left_node
                    while right_node is not None and right_node.customerID == node_temp2.customerID:
                        batchNode[key].add(right_node)
                        temp_nodes.add(right_node)
                        right_node, node_temp2 = right_node.rightNode, right_node
                    key += 1
            else:
                continue
        while not q_unDispatchedNode.empty():
            arriveTime_node_pair = q_unDispatchedNode.get()
            node = arriveTime_node_pair[1]
            flag_no_wait = False
            batch_node = None
            for key in batchNode:
                if node in batchNode[key]:
                    batch_node = batchNode[key]
                    break
            if node.demandType != "parking":
                earliestDepartureTime = node.vehicleArriveTime + timedelta(
                    seconds=gConfig["static_process_time_on_customer"])
            else:
                earliestDepartureTime = node.vehicleArriveTime
            if batch_node:
                for nd in batch_node:
                    earliestDepartureTime += timedelta(seconds=nd.processTime)
            else:
                earliestDepartureTime += timedelta(seconds=node.processTime)

            if datetime.strptime(node.timeWindow[1], "%Y-%m-%d %H:%M:%S") < datetime.strptime(node.timeWindow[0],
                                                                                     "%Y-%m-%d %H:%M:%S"):
                latest_leave_time = datetime.strptime(node.timeWindow[1], "%Y-%m-%d %H:%M:%S") + timedelta(days=1)
            else:
                latest_leave_time = datetime.strptime(node.timeWindow[1], "%Y-%m-%d %H:%M:%S")
            order_creation_time = datetime.strptime(node.timeWindow[0], "%Y-%m-%d %H:%M:%S")
            if node.vehicleArriveTime < order_creation_time:
                return None
            if earliestDepartureTime > latest_leave_time:
                # if tp == "destroy":
                #     assert earliestDepartureTime < latest_leave_time
                return None

            for i in range(self._port_num):
                if len(self._port_reserveTable[i]) == 0:
                    self._port_reserveTable[i].append(node)

                    flag_no_wait = True
                    right_node = self._getRightNode(node, batch_node)
                    if right_node:
                        arrive_time = earliestDepartureTime + \
                                      timedelta(seconds=
                                                travelCost_solver.getTravelCost(right_node.leftNode.customerID,
                                                                                right_node.customerID)["travel_time"])
                        if node.vehicleDepartureTime != earliestDepartureTime or right_node.vehicleArriveTime != arrive_time:
                            right_node.setVehicleArriveTime(arrive_time)
                            nodeList.append(right_node)
                        right_node_temp = right_node
                        while right_node_temp.rightNode and right_node_temp.customerID == right_node_temp.rightNode.customerID:
                            right_node_temp = right_node_temp.rightNode
                            right_node_temp.setVehicleArriveTime(arrive_time)

                    if batch_node:
                        for nd in batch_node:
                            nd.setStartProcessTime(nd.vehicleArriveTime)
                            nd.setVehicleDepartureTime(earliestDepartureTime)
                    else:
                        node.setStartProcessTime(node.vehicleArriveTime)
                        node.setVehicleDepartureTime(earliestDepartureTime)
                    q_dispatchedNode.put((node.vehicleDepartureTime, i))
                    break

                else:
                    continue

            if not flag_no_wait:
                indexes = q_dispatchedNode.get()
                pre_node = self._port_reserveTable[indexes[1]][-1]
                start_process_time = node.vehicleArriveTime
                if pre_node.vehicleDepartureTime > node.vehicleArriveTime and node.demandType != "parking":
                    # print("开始产生等待的时间")
                    node_departure_time = pre_node.vehicleDepartureTime + \
                                          timedelta(seconds=(earliestDepartureTime - node.vehicleArriveTime).seconds)
                    start_process_time = pre_node.vehicleDepartureTime
                else:
                    node_departure_time = earliestDepartureTime
                if node_departure_time <= latest_leave_time:
                    right_node = self._getRightNode(node, batch_node)
                    if right_node:
                        arrive_time = node_departure_time + \
                                      timedelta(seconds=
                                                travelCost_solver.getTravelCost(right_node.leftNode.customerID,
                                                                                right_node.customerID)[
                                                    "travel_time"])
                        if node.vehicleDepartureTime != node_departure_time or right_node.vehicleArriveTime != arrive_time:
                            right_node.setVehicleArriveTime(arrive_time)
                            nodeList.append(right_node)
                        right_node_temp = right_node
                        while right_node_temp.rightNode and right_node_temp.customerID == right_node_temp.rightNode.customerID:
                            right_node_temp = right_node_temp.rightNode
                            right_node_temp.setVehicleArriveTime(arrive_time)
                    if batch_node:
                        for nd in batch_node:
                            nd.setStartProcessTime(start_process_time)
                            nd.setVehicleDepartureTime(node_departure_time)
                    else:
                        node.setStartProcessTime(start_process_time)
                        node.setVehicleDepartureTime(node_departure_time)
                    self._port_reserveTable[indexes[1]].append(node)
                    q_dispatchedNode.put((node.vehicleDepartureTime, indexes[1]))
                else:
                    # print("等待时间过长-------------------------------")
                    return None

        self.gen_node_port_map()
        return nodeList

    def removeRequest(self, requestID):
        self._dispatchedRequests.pop(requestID)

    def feasibleReservePort(self, vehicle, node_index_in_route: int) -> bool:
        """
        :return bool
        """
        node = vehicle.getCurrentRoute[node_index_in_route]
        if node.requestID not in self._dispatchedRequests:
            self._dispatchedRequests[node.requestID] = node

        earliestDepartureTime = node.vehicleArriveTime + timedelta(seconds=node.processTime)
        if node.leftNode.demandType != "depot" and node.leftNode.customerID == node.customerID:
            earliestDepartureTime += timedelta(seconds=gConfig["static_process_time_on_customer"])

        # TODO 此处需要在卡位分配模块写好后，删除下面这条代码
        # node.setVehicleDepartureTime(earliestDepartureTime)
        # return True

        # 同一车次同一个站点的订单集合一定会改变原有node的vehicleDepartureTime
        if node.leftNode.demandType != "depot" and node.leftNode.customerID == node.customerID or \
                node.rightNode and node.rightNode.customerID == node.customerID:
            return False

        # 同一个车次唯一站点的订单
        """判断是否可不需要重新排序即可分配卡位"""
        for i in range(len(self._port_reserveTable)):
            if len(self._port_reserveTable[
                       i]) == 0 or node.vehicleArriveTime >= self._port_reserveTable[i][len(self._port_reserveTable[i])-1].vehicleDepartureTime:
                node.setStartProcessTime(node.vehicleArriveTime)
                node.setVehicleDepartureTime(earliestDepartureTime)
                self._port_reserveTable[i].append(node)
                return True
            else:
                # 判断是否可以插在空隙里
                for j in range(len(self._port_reserveTable[i]) - 1):
                    # print(node.vehicleDepartureTime)
                    if node.vehicleArriveTime >= self._port_reserveTable[i][j].vehicleDepartureTime and \
                            earliestDepartureTime <= self._port_reserveTable[i][j + 1].vehicleArriveTime:
                        node.setStartProcessTime(node.vehicleArriveTime)
                        node.setVehicleDepartureTime(earliestDepartureTime)
                        return True
                    else:
                        continue
        return False

    def releasePort(self, nodes: List[customer_request_combination]):
        """
        当完成装卸货作业后，删除锁定的该时间段，减少分配卡位所需的搜索时间。
        逻辑上nodes应该是在port列表中的第一位
        :param nodes:
        :return:
        """
        if len(nodes) == 1:
            node = nodes[0]
            for i in range(self._port_num):
                if self._port_reserveTable[i][0] == node:
                    del self._port_reserveTable[i][0]
                    break
        elif len(nodes) > 1:
            for i in range(self._port_num):
                if self._port_reserveTable[i][0] in nodes:
                    del self._port_reserveTable[i][0]
                    break
        else:
            print("wrong node for releasePort")

    def addNewDemand(self, orderID: str, demandInfo: dict):
        """
        :param orderID:
        :param demandInfo: creation_time, demandType, volume, brotherCustomer, timeWindow, finishTime, matchedVehicle
        :return:
        """
        self._unfinished_demand_info[orderID] = demandInfo

    def addFinishedDemand(self, orderID, finishTime):
        """
        同时更新未完成需求和已完成需求信息
        :param orderID:
        :param finishTime: 完成时间点
        """
        self._unfinished_demand_info[orderID]["finishTime"] = finishTime
        self._finish_demand_info[orderID] = self._unfinished_demand_info[orderID]
        self._unfinished_demand_info.pop(orderID)
