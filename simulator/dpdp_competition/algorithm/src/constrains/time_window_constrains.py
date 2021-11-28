from datetime import datetime, timedelta

from simulator.dpdp_competition.algorithm.src.constrains.constrains_base import ConstrainsBase
from simulator.dpdp_competition.algorithm.src.common.customer_request_combination import CustomerRequestCombination
from simulator.dpdp_competition.algorithm.conf.configs import Configs
from simulator.dpdp_competition.algorithm.src.utils.route_cost_util import RouteCostBase
from simulator.dpdp_competition.algorithm.src.enum.route_cost_enum import RouteCostEnum
from simulator.dpdp_competition.algorithm.src.enum.demand_info_enum import DemandInfoEnum


class TimeWindowConstrains(ConstrainsBase):

    def __init__(self,
                 pre_node: CustomerRequestCombination,
                 target_customer_id: str,
                 demand_type: str,
                 request: dict,
                 travel_cost_solver: RouteCostBase):
        self.__pre_node = pre_node
        self.__target_customer_id = target_customer_id
        self.__demand_type = demand_type
        self.__request = request
        self.__travel_cost_solver = travel_cost_solver
        self.__node_arrive_time = None

    def isFeasible(self) -> bool:
        demand_info = self.__demand_type + "_demand_info"
        if datetime.strptime(self.__request[demand_info]["time_window"][1], "%Y-%m-%d %H:%M:%S") < datetime.strptime(
                self.__request[demand_info][DemandInfoEnum.time_window.name][0], "%Y-%m-%d %H:%M:%S"):
            latest_leave_time = datetime.strptime(self.__request[demand_info][DemandInfoEnum.time_window.name][1], "%Y-%m-%d %H:%M:%S") \
                                + timedelta(days=1)
        else:
            latest_leave_time = datetime.strptime(self.__request[demand_info][DemandInfoEnum.time_window.name][1], "%Y-%m-%d %H:%M:%S")
        order_creation_time = datetime.strptime(self.__request[demand_info][DemandInfoEnum.time_window.name][0], "%Y-%m-%d %H:%M:%S")
        travel_cost = self.__travel_cost_solver.getTravelCost(self.__pre_node.customerID, self.__target_customer_id)
        arrive_customer_time = self.__pre_node.vehicleDepartureTime + timedelta(seconds=travel_cost[RouteCostEnum.travel_time.name])
        leave_customer_time = arrive_customer_time + timedelta(seconds=self.__request[demand_info][DemandInfoEnum.process_time.name])
        if self.__pre_node.customerID != self.__target_customer_id:
            leave_customer_time += timedelta(seconds=Configs.static_process_time_on_customer)
        is_feasible = True
        if arrive_customer_time < order_creation_time:
            is_feasible = False
        if leave_customer_time > latest_leave_time:
            is_feasible = False
        self.__node_arrive_time = arrive_customer_time
        return is_feasible

    @property
    def get_node_arrive_time(self):
        return self.__node_arrive_time
