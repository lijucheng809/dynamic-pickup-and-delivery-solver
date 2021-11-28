import sys
import time
from copy import deepcopy

from simulator.dpdp_competition.algorithm.src.algo.dpdp_solver import DPDPSolver
from simulator.dpdp_competition.algorithm.data_transfomer.data_transfomer import DataTransformer
from simulator.dpdp_competition.algorithm.conf.configs import Configs
from simulator.dpdp_competition.algorithm.src.utils.request_cluster_util import RequestCluster
from simulator.dpdp_competition.algorithm.src.api.sim_output_converter import SimOutputConverter
from simulator.dpdp_competition.algorithm.src.api.solver_init import SolverInit


def scheduling():
    start_time = time.time()

    '''数据转换'''
    sim_output_converter = SimOutputConverter()
    time_2_go = sim_output_converter.get_go_time
    # todo 新增一个request_attribute enum类
    request_info = sim_output_converter.get_request_info
    new_requests, old_requests_map = RequestCluster.new_requests_cluster(deepcopy(request_info["requests"]))
    print(old_requests_map, file=sys.stderr)

    '''引擎初始化'''
    dpdp_solver = DPDPSolver(old_requests_map)

    SolverInit.pushRequests2Solver(dpdp_solver, new_requests, sim_output_converter.get_customer_id_info_map)
    SolverInit.pushVehicle2Solver(sim_output_converter.get_vehicles_info, dpdp_solver,
                                  sim_output_converter.get_customer_id_info_map,
                                  sim_output_converter.get_ongoing_items_map,
                                  request_info)

    '''调度运算'''
    dpdp_solver.constructEngine(time2Go=time_2_go, CPU_limit=Configs.algo_run_time - 1)  # 初始解(greedy策略)
    middle_tim = time.time()

    if Configs.heuristic_engine:  # ALNS
        left_time_2_heuristic = Configs.algo_run_time - (middle_tim - start_time) / 60. - 0.5
        if len(new_requests) > 10 and left_time_2_heuristic > 3:
            dpdp_solver.heuristicEngine(time2Go=time_2_go, CPU_limit=2)

    '''运算结果输出'''
    vehicles = dpdp_solver.getVehiclesPool
    customers = dpdp_solver.getCustomerPool
    DataTransformer.solution_algo_2_sim(vehicles,
                                        customers,
                                        request_info["requests_items_map"],
                                        sim_output_converter.get_vehicles_info_map,
                                        old_requests_map)


if __name__ == "__main__":
    scheduling()
