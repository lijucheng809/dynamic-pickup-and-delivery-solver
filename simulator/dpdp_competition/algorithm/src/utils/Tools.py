import numpy as np
from time import time
from copy import deepcopy
from rectpack import newPacker
from comment.utils.ProjectConfig import get_mysql_conn
from HexCoordOfCitys.Common.Tools import get_distance_time
from Computation.Tools.CommonTools import get_route_angle_at_certain_position
from comment.utils.Tools import check_distance_time_path_from_two_node_without_db
from comment.utils.VanguardOnline.HexCoordOfCitys.China.Tools import period_judgment
from comment.utils.ProjectConfig import get_mysql_conn, get_network_info_by_user_id


def time_transform(string):
    """8:20转换为分钟数"""
    # 针对没有给出最晚时间的情况,给其一个比较大的值
    if len(string) == 0:
        return 1440
    h, m = string.strip().split(":")

    res = int(h) * 60 + int(m)
    return res


def get_route_cost(route, scenario):
    # 计算route的cost，保存在route内
    route.cost = 100
    return route.cost


def check_vehicle_capacity(route, scenario, vehicle_id):
    vehicle_length = scenario.fleet[vehicle_id]['carriage_length']
    vehicle_width = scenario.fleet[vehicle_id]['carriage_width']
    vehicle_height = scenario.fleet[vehicle_id]['carriage_height']

    update_container_infos = {}
    for tp in route.node_list:
        if tp.node_type != 'dc':
            for tmp_sub_node in tp.sub_nodes:
                container_infos = tmp_sub_node.container_num
                container_code = container_infos.split('(')[0]
                container_size = container_infos.split('(')[1].replace(')', '')
                container_flag = scenario.container_dict[container_code][0]
                if container_flag == 0:  # 0：代表长宽相同和堆叠 ，1：同尺寸可堆叠:
                    container_length_widths = container_size.split('*')
                    key = str(container_length_widths[0]) + '_' + str(container_length_widths[1])
                    if key in update_container_infos.keys():
                        acc_success_flag = False
                        for tmp_height in update_container_infos[key]:
                            tmp_acc_height = tmp_height + float(container_length_widths[2])
                            if tmp_acc_height < vehicle_height:
                                idx = update_container_infos[key].index(tmp_height)
                                update_container_infos[key][idx] += float(container_length_widths[2])
                                acc_success_flag = True
                                break
                        if not acc_success_flag:
                            update_container_infos[key].append(float(container_length_widths[2]))
                    else:
                        update_container_infos[key] = [float(container_length_widths[2])]
                else:
                    container_length_widths = container_size.split('*')
                    key = str(container_length_widths[0]) + '_' + str(container_length_widths[1]) + '_' + str(container_length_widths[2])
                    if key in update_container_infos.keys():
                        acc_success_flag = False
                        for tmp_height in update_container_infos[key]:
                            tmp_acc_height = tmp_height + float(container_length_widths[2])
                            if tmp_acc_height < vehicle_height:
                                idx = update_container_infos[key].index(tmp_height)
                                update_container_infos[key][idx] += float(container_length_widths[2])
                                acc_success_flag = True
                                break
                        if not acc_success_flag:
                            update_container_infos[key].append(float(container_length_widths[2]))
                    else:
                        update_container_infos[key] = [float(container_length_widths[2])]

    rectangles = []

    for key, values in update_container_infos.items():
        tmp_rectangle_nums = len(values)
        tmp_length = float(key.split('_')[0])
        tmp_width = float(key.split('_')[1])
        i = 0
        while i < tmp_rectangle_nums:
            rectangles.append((tmp_length, tmp_width))
            i += 1

    bins = []
    for i in range(0, len(rectangles)):
        bins.append((vehicle_length, vehicle_width))

    flag,  match_length, match_width = rectangles_match_bins(rectangles, bins)

    return flag, match_length, match_width


def rectangles_match_bins(rectangles, bins):
    packer = newPacker()
    for r in rectangles:
        packer.add_rect(*r)
    for b in bins:
        packer.add_bin(*b)
    packer.pack()
    nbins = len(packer)
    if nbins > 1:
        return False, nbins, nbins
    else:
        return True, packer[0].width, packer[0].height


def get_route_load(route, scenario):
    '''
       capacity_type: 1：chill, 2: frozen, 3:dry
    '''

    total_weight = 0
    total_volume = 0

    for node in route.node_list:
        if node.node_type == 'customer':
            total_volume += round(node.volume, 4)
            total_weight += node.weight

    route.total_volume = total_volume
    vehicle = scenario.fleet[route.vehicle_id]
    volume_overload = max([0, route.total_volume - vehicle['volume_capacity']]) / (vehicle['volume_capacity'])
    if volume_overload == 0:
        flag, match_length, match_width = check_vehicle_capacity(route, scenario, route.vehicle_id)   # 计算三维装箱体积
        if not flag:
            route.capacity_violation = 0.5 * match_length  # todo 因为不能摆放而超载的基数，后期可以调整
        else:
            route.capacity_violation = volume_overload
    else:
        route.capacity_violation = volume_overload + 0.5

    route.loading_rate_volume = round(route.total_volume / (vehicle['volume_capacity']), 3)


def comprehensive_time_without_windows(route, scenario, para):

    route.node_list[0].leave_time = 8 * 60
    over_time_violation = push_route_time_by_time_windows(route, scenario)
    if over_time_violation == 0:
        over_time_violation = rewind_route_time_by_time_windows(route, scenario)
    else:
        route_copy = deepcopy(route)
        traffic_restriction_retrodict(route_copy, scenario)
        if route_copy.tmp_over_time < route.tmp_over_time:
            over_time_violation = push_route_time_by_time_windows(route_copy, scenario)
            for idx in range(len(route.node_list)):
                if route.node_list[idx].code != route_copy.node_list[idx].code:
                    print('error**** ')
                route.node_list[idx].arrive_time = route_copy.node_list[idx].arrive_time
                route.node_list[idx].leave_time = route_copy.node_list[idx].leave_time
            route.time_violation = route_copy.time_violation
            route.tmp_over_time = route_copy.tmp_over_time

        elif route_copy.tmp_over_time == route.tmp_over_time:
            if route_copy.time_violation < route.time_violation:
                over_time_violation = push_route_time_by_time_windows(route_copy, scenario)
                for idx in range(len(route.node_list)):
                    if route.node_list[idx].code != route_copy.node_list[idx].code:
                        print('error**** ')
                    route.node_list[idx].arrive_time = route_copy.node_list[idx].arrive_time
                    route.node_list[idx].leave_time = route_copy.node_list[idx].leave_time
                route.time_violation = route_copy.time_violation
                route.tmp_over_time = route_copy.tmp_over_time

    total_time_tmp = 0

    for node_idx in range(1, len(route.node_list)):
        # 比较上一个点的离开时间和当前点的到达时间  ToDo 此处相邻点只考虑跨一天，不考虑跨多天
        if route.node_list[node_idx - 1].leave_time <= route.node_list[node_idx].arrive_time:
            total_time_tmp += route.node_list[node_idx].arrive_time - route.node_list[node_idx - 1].leave_time
            total_time_tmp += route.node_list[node_idx].unloading_time
        else:
            total_time_tmp += route.node_list[node_idx].arrive_time + 1440 - route.node_list[node_idx - 1].leave_time
            total_time_tmp += route.node_list[node_idx].unloading_time

    if para.back_dc:
        period_num = 6
        hex_coord_flag = get_network_info_by_user_id(scenario.user_id)
        distance_dict = scenario.distance_dict
        time_dict = scenario.time_dict
        start_datetime = route.node_list[-1].leave_time
        idx = period_judgment(start_datetime, hex_coord_flag)
        route.node_list[-1].period_flag = idx
        hex_coord_paired = str(route.node_list[-1].hex_coord) + "-" + str(route.node_list[0].hex_coord)
        if hex_coord_paired in distance_dict.keys():
            return_distance = distance_dict[hex_coord_paired][idx]
            if return_distance:
                return_travel_time = (time_dict[hex_coord_paired][idx]) / 60
            else:
                return_distance, time_tmp = get_distance_time(route.node_list[-1], route.node_list[0])
                scenario.distance_dict[hex_coord_paired][idx] = return_distance
                scenario.time_dict[hex_coord_paired][idx] = time_tmp
                return_travel_time = time_tmp / 60

        else:
            return_distance, duration = get_distance_time(route.node_list[-1], route.node_list[0])
            scenario.distance_dict[hex_coord_paired] = [return_distance] * period_num
            scenario.time_dict[hex_coord_paired] = [duration] * period_num
            return_travel_time = duration / 60

        total_time_tmp += return_travel_time
        route.total_distance += return_distance
        route.total_distance_plus_return = route.total_distance

    route.total_time = total_time_tmp

    return


def push_route_time_by_time_windows(route, scenario):
    route_total_distance = 0
    route_duration_time = 0
    over_time_violation = 0
    total_time_windows_violation = 0
    hex_coord_flag = get_network_info_by_user_id(scenario.user_id)
    distance_dict = scenario.distance_dict
    time_dict = scenario.time_dict
    period_num = 6

    for node_index in range(0, len(route.node_list)):
        if node_index == 0:
            leave_time_from_last_node = route.node_list[node_index].leave_time
            start_datetime = leave_time_from_last_node
            idx = period_judgment(start_datetime, hex_coord_flag)
            route.node_list[node_index].period_flag = idx
        else:
            if route.node_list[node_index].id == route.node_list[node_index - 1].id:
                start_datetime = route.node_list[node_index - 1].leave_time
                idx = period_judgment(start_datetime, hex_coord_flag)
                route.node_list[node_index - 1].period_flag = idx
                route.node_list[node_index].arrive_time = route.node_list[node_index - 1].arrive_time
                route.node_list[node_index].leave_time = route.node_list[node_index - 1].leave_time
                route.node_list[node_index].period_flag = idx
                leave_time_from_last_node = route.node_list[node_index - 1].leave_time
            else:
                start_datetime = route.node_list[node_index - 1].leave_time
                idx = period_judgment(start_datetime, hex_coord_flag)
                route.node_list[node_index - 1].period_flag = idx
                hex_coord_paired = str(route.node_list[node_index - 1].hex_coord) + "-" + str(
                    route.node_list[node_index].hex_coord)
                if hex_coord_paired in distance_dict.keys():
                    distance_tmp = distance_dict[hex_coord_paired][idx]
                    if distance_tmp:
                        travel_time = (time_dict[hex_coord_paired][idx]) / 60
                        route_total_distance += distance_tmp
                        route_duration_time += travel_time
                    else:
                        distance, time_tmp = get_distance_time(route.node_list[node_index - 1],
                                                               route.node_list[node_index])
                        scenario.distance_dict[hex_coord_paired][idx] = distance
                        scenario.time_dict[hex_coord_paired][idx] = time_tmp
                        travel_time = time_tmp / 60
                        route_total_distance += distance
                        route_duration_time += travel_time
                else:
                    distance, duration = get_distance_time(route.node_list[node_index - 1], route.node_list[node_index])
                    scenario.distance_dict[hex_coord_paired] = [distance] * period_num
                    scenario.time_dict[hex_coord_paired] = [duration] * period_num
                    travel_time = duration / 60
                    route_total_distance += distance
                    route_duration_time += travel_time

                arrive_time = leave_time_from_last_node + travel_time
                if scenario.user_id not in [91]:
                    if arrive_time >= 24 * 60:
                        arrive_time -= 24 * 60

                min_time_advanced = float('inf')
                min_time_pushed = float('inf')
                chosen_arrive_time = 0
                chosen_leave_time = 0
                tmp_node_time_windows = route.node_list[node_index].time_windows
                if route.node_list[node_index].unloading_time == None:
                    route.node_list[node_index].unloading_time = 30

                route_duration_time += route.node_list[node_index].unloading_time

                ###对于有多个时间窗的，取时间窗gap 最小的情况：
                if scenario.user_id == 91 and not tmp_node_time_windows:
                    tmp_node_time_windows = [{"et": 0, "lt": 1440}]

                for tmp_time_window in tmp_node_time_windows:
                    tmp_time_advanced = 0
                    tmp_time_pushed = 0
                    tmp_arrive_time = arrive_time
                    # print('tmp_time_windows: ', tmp_time_window['et'])
                    if tmp_time_window['et'] != None:
                        # print('tmp_arrive_time:', tmp_arrive_time, tmp_time_window['et'])
                        if tmp_time_window['et'] > tmp_arrive_time:
                            tmp_time_advanced = tmp_time_window['et'] - arrive_time
                            tmp_arrive_time = tmp_time_window['et']
                        else:
                            tmp_gap = abs(tmp_arrive_time - tmp_time_window['et'])
                            tmp_gap_2 = abs((tmp_arrive_time - 24 * 60) - tmp_time_window['et'])
                            # if scenario.user_id not in [91, 80, 90]:
                            #     if tmp_gap > tmp_gap_2:
                            #         tmp_arrive_time = tmp_time_window['et']
                            #         tmp_time_advanced = tmp_gap_2

                    if scenario.user_id not in [91]:
                        if tmp_arrive_time >= 24 * 60:
                            tmp_arrive_time -= 24 * 60

                    if node_index == 1:
                        tmp_time_advanced = 0

                    tmp_leave_time = tmp_arrive_time + route.node_list[node_index].unloading_time
                    cross_day_flag = False
                    if scenario.user_id not in [91]:
                        if tmp_leave_time >= 24 * 60:
                            tmp_leave_time -= 24 * 60
                            cross_day_flag = True

                    if tmp_time_window['lt'] != None:
                        if cross_day_flag:
                            if tmp_time_window['lt'] < tmp_time_window['et']:
                                if tmp_time_window['lt'] < tmp_leave_time:
                                    tmp_time_pushed = tmp_leave_time - tmp_time_window['lt']
                            else:
                                if tmp_time_window['lt'] < tmp_leave_time + 24 * 60:
                                    tmp_time_pushed = tmp_leave_time + 24 * 60 - tmp_time_window['lt']
                        else:
                            if tmp_time_window['lt'] < tmp_leave_time:
                                tmp_time_pushed = tmp_leave_time - tmp_time_window['lt']

                    if min_time_pushed > tmp_time_pushed:
                        min_time_pushed = tmp_time_pushed
                        min_time_advanced = tmp_time_advanced
                        chosen_arrive_time = tmp_arrive_time
                        chosen_leave_time = tmp_leave_time

                    elif tmp_time_pushed == min_time_pushed:
                        if tmp_time_advanced < min_time_advanced:
                            min_time_advanced = tmp_time_advanced
                            chosen_arrive_time = tmp_arrive_time
                            chosen_leave_time = tmp_leave_time

                route.node_list[node_index].arrive_time = chosen_arrive_time
                route.node_list[node_index].leave_time = chosen_leave_time
                leave_time_from_last_node = route.node_list[node_index].leave_time
                total_time_windows_violation += 5 * (min_time_advanced / 10) ** 2 + 1000 * (min_time_pushed / 2) ** 3
                over_time_violation += 1000 * (min_time_pushed / 2) ** 3

    route.time_violation = total_time_windows_violation
    route.tmp_over_time = over_time_violation
    route.total_distance = route_total_distance
    route.total_time = route_duration_time

    return over_time_violation


def rewind_route_time_by_time_windows(route, scenario):
    hex_coord_flag = get_network_info_by_user_id(scenario.user_id)
    distance_dict = scenario.distance_dict
    time_dict = scenario.time_dict
    period_num = 6
    total_time_windows_violation = 0
    over_time_violation = 0
    total_distance = 0
    standard_unloading_time = 30
    if route.node_list[-1].unloading_time != None:
        standard_unloading_time = route.node_list[-1].unloading_time

    total_duration = standard_unloading_time
    end_datetime = route.node_list[-1].arrive_time
    # print('route.node_list: ', route.node_list[-1].arrive_time)

    for tmp_idx in range(len(route.node_list) - 2, -1, -1):
        if route.node_list[tmp_idx].code == route.node_list[tmp_idx + 1]:
            route.node_list[tmp_idx].leave_time = route.node_list[tmp_idx + 1].leave_time
            route.node_list[tmp_idx].arrive_time = route.node_list[tmp_idx + 1].arrive_time
            continue
        if route.node_list[tmp_idx].unloading_time != None:
            standard_unloading_time = route.node_list[tmp_idx].unloading_time

        if scenario.user_id not in [91]:
            if end_datetime < 0:  ##倒推跨天的时候
                end_datetime += 24 * 60

        idx = period_judgment(end_datetime, scenario.network_dict)
        hex_coord_paired = str(route.node_list[tmp_idx].hex_coord) + "-" + str(route.node_list[tmp_idx + 1].hex_coord)

        if hex_coord_paired in distance_dict.keys():
            distance = distance_dict[hex_coord_paired][idx]
            if distance:
                time_tmp = time_dict[hex_coord_paired][idx]
                total_distance += distance
                total_duration += time_tmp

            else:
                distance, time_tmp = get_distance_time(route.node_list[tmp_idx], route.node_list[tmp_idx + 1])
                scenario.distance_dict[hex_coord_paired][idx] = distance
                scenario.time_dict[hex_coord_paired][idx] = time_tmp
                total_distance += distance
        else:
            distance, time_tmp = get_distance_time(route.node_list[tmp_idx], route.node_list[tmp_idx + 1])
            scenario.distance_dict[hex_coord_paired] = [distance] * period_num
            scenario.time_dict[hex_coord_paired] = [time_tmp] * period_num
            total_distance += distance

        end_datetime = end_datetime - time_tmp / 60  # todo 倒推出leave node1的时间, 因此此时需要和node1的时间窗做交集判断

        if scenario.user_id not in [91]:
            if end_datetime < 0:
                end_datetime += 24 * 60
            ##即为dc, dc 没有目前没有给时间窗：
        if tmp_idx == 0:
            route.node_list[tmp_idx].leave_time = end_datetime
            route.transport_time = route.node_list[tmp_idx].leave_time  ##dc的最晚离开时间即为发车时间
            continue
        ##再进行时间窗的选择：
        min_time_advanced = float('inf')
        min_time_pushed = float('inf')
        chosen_arrive_time = 0
        chosen_leave_time = 0
        tmp_node_time_windows = route.node_list[tmp_idx].time_windows
        if scenario.user_id == 91 and not tmp_node_time_windows:
            tmp_node_time_windows = [{"et": 0, "lt": 1440}]
        ###对于有多个时间窗的，取时间窗gap 最小的情况：
        for tmp_time_window in tmp_node_time_windows:
            tmp_time_advanced = 0
            tmp_time_pushed = 0
            tmp_current_leave_time = end_datetime
            # print('tmp_current_leave_time::: ', tmp_current_leave_time)
            if tmp_time_window['lt'] != None:
                if tmp_time_window['lt'] < tmp_current_leave_time:
                    tmp_time_advanced = tmp_current_leave_time - tmp_time_window['lt']  ##前面的点至少要等的时间
                    tmp_current_leave_time = tmp_time_window['lt']
                else:
                    tmp_gap_1 = abs(tmp_time_window['lt'] - tmp_current_leave_time)
                    tmp_gap_2 = abs(tmp_time_window['lt'] - (tmp_current_leave_time + 24 * 60))  ##跨天leave_time校验
                    # if scenario.user_id not in [91, 80, 90]:
                    #     if tmp_gap_1 > tmp_gap_2:
                    #         tmp_current_leave_time = tmp_time_window['lt']
                    #         tmp_time_advanced = tmp_gap_2
                    # else:
                    #     tmp_time_advanced = tmp_gap_1

            if scenario.user_id not in [91]:
                if tmp_current_leave_time < 0:
                    tmp_current_leave_time += 24 * 60

            tmp_current_arrive_time = tmp_current_leave_time - standard_unloading_time  ##最晚达到的时间
            if scenario.user_id not in [91]:
                if tmp_current_arrive_time < 0:
                    tmp_current_arrive_time += 24 * 60

            if tmp_time_window['et'] != None:
                if tmp_time_window['et'] > tmp_current_arrive_time:  ##说明最晚到达时间不包含再current node 的时间窗中，需要重惩罚
                    tmp_time_pushed = tmp_time_window['et'] - tmp_current_arrive_time

            if min_time_pushed > tmp_time_pushed:
                min_time_pushed = tmp_time_pushed
                min_time_advanced = tmp_time_advanced
                chosen_arrive_time = tmp_current_arrive_time
                chosen_leave_time = tmp_current_leave_time

            elif tmp_time_pushed == min_time_pushed:
                if tmp_time_advanced < min_time_advanced:
                    min_time_advanced = tmp_time_advanced
                    chosen_arrive_time = tmp_current_arrive_time
                    chosen_leave_time = tmp_current_leave_time

        route.node_list[tmp_idx].arrive_time = chosen_arrive_time
        route.node_list[tmp_idx].leave_time = chosen_leave_time
        end_datetime = route.node_list[tmp_idx].arrive_time
        # print('** min_time_advanced: ', route.node_list[tmp_idx].code,  min_time_advanced, 'min_time_pushed: ', min_time_pushed)
        total_time_windows_violation += 5 * (min_time_advanced / 10) ** 2 + 1000 * (min_time_pushed / 2) ** 3
        over_time_violation += 1000 * (min_time_pushed / 2) ** 3

    route.time_violation = total_time_windows_violation
    route.tmp_over_time = over_time_violation
    route.total_distance = total_distance

    return over_time_violation


def traffic_restriction_retrodict(route, scenario):
    """通过限行区逆向倒推一个推荐时间：
    """
    period_num = len(scenario.network_dict["time_segment"])  # 路网划分的时段个数
    total_distance = 0  # 米
    total_duration = 0  # 秒
    # 计算相关违反指标
    distance_dict = scenario.distance_dict
    time_dict = scenario.time_dict
    # 每个点的统一/标准卸货时间，分钟
    standard_unloading_time = scenario.fleet[route.vehicle_id]['standard_unloading_time']  ##在门店站点本身没有卸货时间的情况下用标准的卸货时长
    total_time_windows_violation = 0
    over_time_violation = 0

    rt_lt_indexes = [route.node_list.index(tp) for tp in route.node_list if
                     tp.node_type != 'dc' and tp.time_windows[0]['lt'] != None]

    if len(rt_lt_indexes) == 0:  ##此时剔除了某一路线都没有时间窗要求的情况
        recommend_departure_time = None
        route.transport_time = recommend_departure_time
        return route

    else:
        rt_lt_indexes.sort(reverse=True)
        last_lt_node_idx = rt_lt_indexes[0]
        need_update_rt_nodes = route.node_list[0: last_lt_node_idx + 1]
        left_update_rt_nodes = route.node_list[last_lt_node_idx + 1:]

        if len(need_update_rt_nodes[-1].time_windows) == 2:
            if need_update_rt_nodes[-1].time_windows[1]['lt'] == 1440 and need_update_rt_nodes[-1].time_windows[0][
                'et'] == 0:  ##说明两个时间窗是相连接的
                end_datetime = need_update_rt_nodes[-1].time_windows[0]['lt']  ##选择凌晨的时间窗
            else:
                end_datetime = need_update_rt_nodes[-1].time_windows[0]['lt']  ##任意选择一个时间窗
        else:
            end_datetime = need_update_rt_nodes[-1].time_windows[0]['lt']

        if need_update_rt_nodes[-1].unloading_time:
            standard_unloading_time = need_update_rt_nodes[-1].unloading_time

        need_update_rt_nodes[-1].leave_time = end_datetime
        need_update_rt_nodes[-1].arrive_time = end_datetime - standard_unloading_time
        end_datetime -= standard_unloading_time

        ## 整个for 循环是从倒数第二个门店开始的：
        for tmp_idx in range(len(need_update_rt_nodes) - 2, -1, -1):
            if need_update_rt_nodes[tmp_idx].code == need_update_rt_nodes[tmp_idx - 1]:
                need_update_rt_nodes[tmp_idx - 1].leave_time = need_update_rt_nodes[tmp_idx].leave_time
                need_update_rt_nodes[tmp_idx - 1].arrive_time = need_update_rt_nodes[tmp_idx].arrive_time
                continue

            if need_update_rt_nodes[tmp_idx].unloading_time:
                standard_unloading_time = need_update_rt_nodes[tmp_idx].unloading_time

            if scenario.user_id not in [91]:
                if end_datetime < 0:  ##倒推跨天的时候
                    end_datetime += 24 * 60

            idx = period_judgment(end_datetime, scenario.network_dict)
            hex_coord_paired = str(need_update_rt_nodes[tmp_idx].hex_coord) + "-" + str(
                need_update_rt_nodes[tmp_idx + 1].hex_coord)

            if hex_coord_paired in distance_dict.keys():
                distance = distance_dict[hex_coord_paired][idx]
                if distance:
                    time_tmp = time_dict[hex_coord_paired][idx]
                    total_distance += distance
                    total_duration += time_tmp
                else:
                    distance, time_tmp = get_distance_time(need_update_rt_nodes[tmp_idx],
                                                           need_update_rt_nodes[tmp_idx + 1])
                    scenario.distance_dict[hex_coord_paired][idx] = distance
                    scenario.time_dict[hex_coord_paired][idx] = time_tmp
                    total_distance += distance
                    total_duration += time_tmp
            else:
                distance, time_tmp = get_distance_time(need_update_rt_nodes[tmp_idx], need_update_rt_nodes[tmp_idx + 1])
                scenario.distance_dict[hex_coord_paired] = [distance] * period_num
                scenario.time_dict[hex_coord_paired] = [time_tmp] * period_num
                total_distance += distance
                total_duration += time_tmp

            end_datetime = end_datetime - time_tmp / 60  # todo 倒推出leave node1的时间, 因此此时需要和node1的时间窗做交集判断
            # print('***end_datetime: ', end_datetime)

            if scenario.user_id not in [91]:
                if end_datetime < 0:
                    end_datetime += 24 * 60

            ##即为dc, dc 没有目前没有给时间窗：
            if tmp_idx == 0:
                # print('!!!: ', end_datetime)
                need_update_rt_nodes[tmp_idx].leave_time = end_datetime
                route.transport_time = need_update_rt_nodes[tmp_idx].leave_time  ##dc的最晚离开时间即为发车时间
                continue

            ##再进行时间窗的选择：
            min_time_advanced = float('inf')
            min_time_pushed = float('inf')
            chosen_arrive_time = 0
            chosen_leave_time = 0

            tmp_node_time_windows = need_update_rt_nodes[tmp_idx].time_windows
            ###对于有多个时间窗的，取时间窗gap 最小的情况：
            for tmp_time_window in tmp_node_time_windows:
                tmp_time_advanced = 0
                tmp_time_pushed = 0
                tmp_current_leave_time = end_datetime
                if tmp_time_window['lt'] != None:
                    if tmp_time_window['lt'] < tmp_current_leave_time:
                        tmp_time_advanced = tmp_current_leave_time - tmp_time_window['lt']  ##前面的点至少要等的时间
                        tmp_current_leave_time = tmp_time_window['lt']
                    else:
                        tmp_gap_1 = abs(tmp_time_window['lt'] - tmp_current_leave_time)
                        tmp_gap_2 = abs(tmp_time_window['lt'] - (tmp_current_leave_time + 24 * 60))  ##跨天leave_time校验
                        # if scenario.user_id not in [91, 80, 90]:
                        #     if tmp_gap_1 > tmp_gap_2:
                        #         tmp_current_leave_time = tmp_time_window['lt']
                        #         tmp_time_advanced = tmp_gap_2
                        # # else:
                        #     tmp_time_advanced = tmp_gap_1

                if scenario.user_id not in [91]:
                    if tmp_current_leave_time < 0:
                        tmp_current_leave_time += 24 * 60

                tmp_current_arrive_time = tmp_current_leave_time - standard_unloading_time  ##最晚达到的时间

                if scenario.user_id not in [91]:
                    if tmp_current_arrive_time < 0:
                        tmp_current_arrive_time += 24 * 60

                if tmp_time_window['et'] != None:
                    if tmp_time_window['et'] > tmp_current_arrive_time:  ##说明最晚到达时间不包含再current node 的时间窗中，需要重惩罚
                        tmp_time_pushed = tmp_time_window['et'] - tmp_current_arrive_time

                # print('*** route.node_list[node_index]: ', need_update_rt_nodes[tmp_idx].code, tmp_time_pushed,
                #       tmp_current_arrive_time, tmp_time_window['et'])

                if min_time_pushed > tmp_time_pushed:
                    min_time_pushed = tmp_time_pushed
                    min_time_advanced = tmp_time_advanced
                    chosen_arrive_time = tmp_current_arrive_time
                    chosen_leave_time = tmp_current_leave_time

                elif tmp_time_pushed == min_time_pushed:
                    if tmp_time_advanced < min_time_advanced:
                        min_time_advanced = tmp_time_advanced
                        chosen_arrive_time = tmp_current_arrive_time
                        chosen_leave_time = tmp_current_leave_time

            # print('route.need_update_rt_nodes: ', need_update_rt_nodes[tmp_idx].code,chosen_leave_time, chosen_arrive_time)

            need_update_rt_nodes[tmp_idx].arrive_time = chosen_arrive_time
            need_update_rt_nodes[tmp_idx].leave_time = chosen_leave_time
            end_datetime = need_update_rt_nodes[tmp_idx].arrive_time
            # print('end_date_time: ', end_datetime)

            # print('!! min_time_advanced: ', need_update_rt_nodes[tmp_idx].code, min_time_advanced, 'min_time_pushed: ', min_time_pushed)
            total_time_windows_violation += 5 * (min_time_advanced / 10) ** 2 + 1000 * (min_time_pushed / 2) ** 3
            over_time_violation += 1000 * (min_time_pushed / 2) ** 3

        route.time_violation = total_time_windows_violation
        route.tmp_over_time = over_time_violation
        route.over_time_violation = over_time_violation

        ##则剩下的没有时间窗要求的门店，按照限行区往后顺推：
        if len(left_update_rt_nodes) > 0:
            ##不改变last_node 的leave_time, 后延下一个点的arrive_time
            for tmp_idx in range(len(left_update_rt_nodes)):
                if tmp_idx == 0:
                    start_datetime = need_update_rt_nodes[-1].leave_time
                    last_node = need_update_rt_nodes[-1]
                else:
                    start_datetime = left_update_rt_nodes[tmp_idx - 1].leave_time
                    last_node = left_update_rt_nodes[tmp_idx - 1]

                idx = period_judgment(start_datetime, scenario.network_dict)
                hex_coord_paired = str(last_node.hex_coord) + "-" + str(left_update_rt_nodes[tmp_idx].hex_coord)

                wait_time = 0  # 限行等待时间
                if hex_coord_paired in distance_dict.keys():
                    distance = distance_dict[hex_coord_paired][idx]
                    if distance:
                        time_tmp = time_dict[hex_coord_paired][idx]
                        total_distance += distance
                        total_duration += time_tmp
                    else:
                        distance, time_tmp = get_distance_time(last_node, left_update_rt_nodes[tmp_idx])
                        scenario.distance_dict[hex_coord_paired][idx] = distance
                        scenario.time_dict[hex_coord_paired][idx] = time_tmp
                        total_distance += distance
                        total_duration += time_tmp
                else:
                    distance, time_tmp = get_distance_time(last_node, left_update_rt_nodes[tmp_idx])
                    scenario.distance_dict[hex_coord_paired] = [distance] * period_num
                    scenario.time_dict[hex_coord_paired] = [time_tmp] * period_num
                    total_distance += distance
                    total_duration += time_tmp

                last_node.period_flag = idx

                if left_update_rt_nodes[tmp_idx].unloading_time:  # 如果node设置了卸货时间，则覆盖标准卸货时间
                    standard_unloading_time = left_update_rt_nodes[tmp_idx].unloading_time

                left_update_rt_nodes[tmp_idx].arrive_time = start_datetime + time_tmp / 60
                left_update_rt_nodes[tmp_idx].leave_time = left_update_rt_nodes[
                                                               tmp_idx].arrive_time + standard_unloading_time

        total_time_tmp = 0
        for node_idx in range(1, len(route.node_list)):
            # 比较上一个点的离开时间和当前点的到达时间  ToDo 此处相邻点只考虑跨一天，不考虑跨多天
            if route.node_list[node_idx - 1].leave_time <= route.node_list[node_idx].arrive_time:
                total_time_tmp += route.node_list[node_idx].leave_time - route.node_list[node_idx - 1].leave_time
            else:
                total_time_tmp += (1440 - route.node_list[node_idx - 1].leave_time) + route.node_list[
                    node_idx].leave_time
        total_time = total_time_tmp
        # total_time = route.node_list[-1].leave_time - route.node_list[0].leave_time
        if total_time < 0:
            total_time += 24 * 60
        route.total_time = total_time


def get_fixed_routes_infos(user_id):
    """返回所有固定路线的门店code列表，便于再配载时进行过滤"""
    from comment.utils.ProjectConfig import get_mysql_conn
    import pandas as pd
    fixed_route_code_list = []
    conn = get_mysql_conn()
    fixed_routes = pd.read_sql_query('select name, id from fixed_route where user_id = %d' %(user_id), conn)
    ids = tuple(fixed_routes['id'].unique().tolist())
    sql = 'select code, fixed_route_id from fixed_route_node where fixed_route_id in '+ str(ids)
    nodes_code = pd.read_sql_query(sql, conn)
    nodes_code = nodes_code.rename(columns={'fixed_route_id': 'id'})
    fixed_routes = pd.merge(fixed_routes, nodes_code, how='left', on='id')
    fixed_routes_infos = fixed_routes.groupby('name')['code'].apply(list).to_dict()
    conn.close()
    return fixed_routes_infos


def get_each_area_info_and_neighbor(user_id):
    """获取当前项目配置的区域的领域关系
        :param user_id: 项目的唯一标识
        :return:
    """
    conn = get_mysql_conn()
    cursor = conn.cursor()
    # 获取区域表中的区域偏好信息
    sql = """select id,name,step from area where user_id=%d AND type = 2""" % user_id
    cursor.execute(sql)
    rows = cursor.fetchall()
    area_dict = {}
    for row in rows:
        step = []
        for st in eval(row[2]):
            step.append((st['lng'], st['lat']))
        area_dict[row[0]] = {"name": row[1], "step": step}
    # 获取领域表中的普通领域和优先领域
    sql2 = """select area_id,adjacent_id,type from adjacent_area"""
    cursor.execute(sql2)
    lines = cursor.fetchall()
    neighbors_dict = {}
    for line in lines:
        if line[0] in area_dict:
            if line[0] not in neighbors_dict:
                neighbors_dict[line[0]] = {"neighbor": [], "normal_neighbor": []}
            if line[2] == 2:  # 优先领域
                neighbors_dict[line[0]]["neighbor"].append(area_dict[line[1]]["name"])
            else:  # 普通领域
                neighbors_dict[line[0]]["normal_neighbor"].append(area_dict[line[1]]["name"])

    area_info_list = []
    for k, v in area_dict.items():
        name = v["name"]
        step = deepcopy(v["step"])
        neighbor = []
        normal_neighbor = []
        if k in neighbors_dict:
            neighbor = deepcopy(neighbors_dict[k]["neighbor"])
            normal_neighbor = deepcopy(neighbors_dict[k]["normal_neighbor"])
        area_info_list.append({"steps": step, "name": name, "area_neighbor": neighbor,
                               "normal_neighbor": normal_neighbor})

    conn.close()
    cursor.close()
    # print('area_info_list: ', area_info_list)
    for tmp in area_info_list:
        print('name: ', tmp['name'], '  area_neighbor: ', tmp['area_neighbor'])

    return area_info_list


def evaluate_insertion_feasibility(rand_node, route, scenario, para):
    """
    根据Switch配置的检查项，依次检查。当检查到infeasible就立刻返回0
    各检查项根据校验速度由快到慢排序，提升检查效率
    当通过所有的校验项都没有提前return 0,说明可行，最终return 1
    """
    # 12.3修改：因为re_optimize可能会导致相同的node在同一条route中出现
    # 因此，在insertion的时候需要区分：如果candidate_node不存在于目标route内，与之前无异
    # 而如果candidate_node已经在目标route内了，只需要检查capacity，其他的都不需要check（因为新的node相当于"附体"到了route中的某个node上去了）
    node_multiple_occurrence = False
    for node in route.node_list:
        if rand_node.id == node.id:
            node_multiple_occurrence = True
            break

    if para.route_max_capacity_switch:
        total_box = 0
        total_volume = 0
        total_pallet = 0
        total_weight = 0
        for node in route.node_list:
            if node.node_type == 'customer':  # 排除对DC进行累加
                total_box += node.box
                total_weight += node.weight
                total_pallet += node.pallet
                total_volume += node.volume

        if total_box + rand_node.box > scenario.fleet[route.vehicle_id]['box_capacity']:
            return 0
        if total_pallet + rand_node.pallet > scenario.fleet[route.vehicle_id]['pallet_capacity']:
            return 0
        if total_weight + rand_node.weight > scenario.fleet[route.vehicle_id]['weight_capacity']:
            return 0
        if total_volume + rand_node.volume > scenario.fleet[route.vehicle_id]['volume_capacity']:
            return 0

    # if len(route.node_list) + 1 == 2:
    #     return 1

    if not node_multiple_occurrence:  # 只有node不重复出现的时候，才有必要检查下面这些项目
        if para.time_window_switch:
            # 检查time window
            if str(route.node_list[-1].id) + "-" + str(rand_node.id) in scenario.time_dict:
                traverse_time = scenario.time_dict[str(route.node_list[-1].id) + "-" + str(rand_node.id)]
            else:
                distance,traverse_time,path = check_distance_time_path_from_two_node_without_db(route.node_list[-1],rand_node,scenario)
                scenario.time_dict[str(route.node_list[-1].id) + "-" + str(rand_node.id)] = traverse_time
                scenario.distance_dict[str(route.node_list[-1].id) + "-" + str(rand_node.id)] = distance
            if scenario.windows[rand_node.id][-1]['lt'] != None:
                if route.finish_time + traverse_time > scenario.windows[rand_node.id][-1]['lt']:
                    return 0

        if para.route_max_distance_switch:
            if len(route.node_list) > 2:  # 避免当前只有一个dc,却什么点也插不进来的情况
                # 检查route最大里程：注意，暂时没有包含返程。如果需要，可以将下面的total_distance替换成total_distance_plus_return
                if str(route.node_list[-1].id) + "-" + str(rand_node.id) in scenario.distance_dict.keys():
                    traverse_distance = scenario.distance_dict[str(route.node_list[-1].id) + "-" + str(rand_node.id)]
                else:
                    traverse_distance,duration,path = check_distance_time_path_from_two_node_without_db(route.node_list[-1],rand_node,scenario)
                    scenario.distance_dict[str(route.node_list[-1].id) + "-" + str(rand_node.id)] = traverse_distance
                    scenario.time_dict[str(route.node_list[-1].id) + "-" + str(rand_node.id)] = duration
                if route.total_distance + traverse_distance > para.max_route_distance:
                    return 0

        if para.route_max_node_num_switch:
            # 检查路线中点的数量
            if len(route.node_list) - 1 + 1 > para.max_node_number:  # DC减一，当前inserted node加一
                return 0

        if para.route_max_duration_switch:
            if len(route.node_list) > 1:  # 避免当前只有一个dc,却什么点也插不进来的情况
                # 检查路线最长行驶时长
                # print('当前校验的插入点为：', rand_node.id)
                if str(route.node_list[-1].id) + "-" + str(rand_node.id) in scenario.time_dict:
                    traverse_time = scenario.time_dict[str(route.node_list[-1].id) + "-" + str(rand_node.id)]
                else:
                    dis,traverse_time,path = check_distance_time_path_from_two_node_without_db(route.node_list[-1],rand_node,scenario)
                    scenario.time_dict[str(route.node_list[-1].id) + "-" + str(rand_node.id)] = traverse_time
                    scenario.time_dict[str(route.node_list[-1].id) + "-" + str(rand_node.id)] = dis
                # print('插入前，route duration = ', route.total_time, ' 插入后， route duration = ', route.total_time + traverse_time)
                if route.total_time + traverse_time > para.maximum_route_duration:
                    return 0

        if para.route_max_interval_switch:
            if len(route.node_list) > 1:  # 避免当前只有一个dc,却什么点也插不进来的情况
                # 门店之间最大间隔
                if str(route.node_list[-1].id) + "-" + str(rand_node.id) in scenario.distance_dict.keys():
                    traverse_distance = scenario.distance_dict[str(route.node_list[-1].id) + "-" + str(rand_node.id)]
                else:
                    traverse_distance,duration,path = check_distance_time_path_from_two_node_without_db(route.node_list[-1],rand_node,scenario)
                    scenario.distance_dict[str(route.node_list[-1].id) + "-" + str(rand_node.id)] = traverse_distance
                    scenario.time_dict[str(route.node_list[-1].id) + "-" + str(rand_node.id)] = duration
                if para.interval_limit > rand_node.dynamic_intervals:  # 添加动态最大门店间隔
                    max_interval_limit = para.interval_limit
                else:
                    max_interval_limit = rand_node.dynamic_intervals

                if traverse_distance > max_interval_limit:
                    # print("最大门店间隔", traverse_distance, para.interval_limit)
                    return 0

                elif para.interval_limit < traverse_distance <= para.compatible_list_size:  # 当interval过大时，进一步检查是否"顺路"，如果顺路则可以豁免
                    temp_route = deepcopy(route)
                    temp_route.node_list.append(rand_node)
                    current_position_angle = get_route_angle_at_certain_position(temp_route, len(temp_route.node_list)-1)  # 校验路线在最后一个点处的interval即可。最后一个点的index=len(temp_route.node_list)-1
                    # get_route_max_angle(temp_route)
                    if current_position_angle > para.max_angle_limit:
                        print('既不顺路，又超interval，判定为infeasible insertion')
                        return 0

    if route.vehicle_id not in rand_node.suitable_vehicles:
        # print("路线的vehicle_id %d 不在此插入门店的可用车型里"% route.vehicle_id,rand_node.suitable_vehicles,"判定为infeasible insertion" )
        return 0

    return 1


def traffic_restriction():
    pass


def find_nearest_neighbor_for_route(current_route, unserved_node_list, scenario):
    # 改成一定随机性的k-nearest neighbor，不一定取最近的那个点，而是在最近的几个点中随机选择一个
    last_node = current_route.node_list[-1]
    chosen_node = None
    tmp_min_distance = float('inf')
    for node in unserved_node_list:
        if str(last_node.id) == str(node.id):  # 此处会有相同id的值出现，目前为了让算法跑下去,门店id值相同，则距离为0
            dis = 0
            chosen_node = node
            tmp_min_distance = 0
            break
        if str(last_node.id) + '-' + str(node.id) in scenario.distance_dict.keys():
            dis = scenario.distance_dict[str(last_node.id) + '-' + str(node.id)]
        else:
            dis, duration, path = check_distance_time_path_from_two_node_without_db(last_node, node,scenario)
            scenario.distance_dict[str(last_node.id) + '-' + str(node.id)] = dis  # 从百度获取距离时间后，储存到scenario
            scenario.time_dict[str(last_node.id) + '-' + str(node.id)] = duration

        if tmp_min_distance > dis:
            chosen_node = node
            tmp_min_distance = dis

    return chosen_node  # 返回类型：Node




