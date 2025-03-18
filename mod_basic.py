from .setup import *
from .model import ModelItem
import requests
import re
import time
import cloudscraper
import html
import os
import json
from tool import ToolNotify
import traceback
from datetime import datetime
site_map = {
    '대한통운' : {
        'summary' : {
            'url' : 'https://trace.cjlogistics.com/next/rest/selectTrackingWaybil.do',
            'method' : 'post',
            'data' : {
                'wblNo' : '{track_no}'
            },
            'result_key' : {
                'data.acprNm' : 'to',
                'data.sndrNm' : 'from',
                'data.repGoodsNm' : 'item_name'
            }
        },
        'tracking' : {
            'url' : 'https://trace.cjlogistics.com/next/rest/selectTrackingDetailList.do',
            'method' : 'post',
            'data' : {
                'wblNo' : '{track_no}'
            },
            'result_key' : {
                'data.svcOutList' : 'tracking_list',
            },
            'datetime_key' : {
                'date' : 'workDt',
                'time' : 'workHms'
            },
            'status_key' : 'crgStDnm',
            'tracking_location_key' : 'branNm'
        },
        'type' : 'json',
    },
    '경동택배' : {
        'summary' : {
            'url' : 'https://kdexp.com/service/delivery/ajax_basic.do?barcode={track_no}',
            'result_key' : {
                'info.branch_start' : 'from',
                'info.branch_end' : 'to',
                'info.prod' : 'item_name',
                'info.pd_dt' : 'datetime'
            }
        },
        'tracking' : {
            'url' : 'https://kdexp.com/service/delivery/ajax_basic.do?barcode={track_no}',
            'result_key' : {
                'items' : "tracking_list"
            }, 
            'datetime_key' : "reg_date",
            'status_key' : 'stat',
            'tracking_location_key' : 'location'
        },
        'type' : 'json',
        'time_format' : "%Y-%m-%d %H:%M:%S"
    },
    '한진택배' : {
        'url' : 'https://www.hanjin.com/kor/CMS/DeliveryMgr/WaybillResult.do?mCode=MN038&schLang=KR&wblnumText2={track_no}',
        'type' : 'html',
        'regex_info' : r'<p class=\"cal-sec\"><span class=\"date\">(?P<date>[\d\-]{10})</span>\s<span class=\"time\">(?P<time>[\d\:]{5})</span></p>[\W\S]+?<strong>(?P<status>\w+)</strong>[\W\S]+?data-label=\"상품명\">(?P<item_name>.*)</td>\s+<td data-label=\"보내는 분\">(?P<from>.+)</td>\s+<td data-label=\"받는 분\">(?P<to>.+)',
        'datetime_key' : {
            'date' : 'date',
            'time' : 'time'
        },
        'regex_tracking' : r'<td class=\"w-org\">(?P<tracking_location>[\w\s]+)</td>[\W\S]+?<span class=\"stateDesc\">(?P<tracking_status>.+)</span>',
        'time_format' : '%Y.%m.%d %H:%M',
        'order' : 'asc'
    },
    '우체국택배' : {
        'url' : 'https://service.epost.go.kr/trace.RetrieveDomRigiTraceList.comm?displayHeader=N&sid1={track_no}',
        'type' : 'html',
        'regex_info' : r'<tbody>\s+<tr>[\W\S]+?<td>(?P<from>[\w\*]+)[\W\S]+?<td>(?P<to>[\w\*]+)[\W\S]+?<td>(?P<item_name>[\w\s]+)</td>[\W\S]+?(?P<status>[\w\s]+)</td>\s+</tr>',
        'regex_tracking' : r'<tr>[\W\S]+?<td>(?P<date>[\d\.]{10})</td>\s+<td>(?P<time>[\d\:]{5})</td>\s+<td>(?P<tracking_location>[\W\S]+?)</td>\s+<td>\s+<span class=\"evtnm\">(?P<tracking_status>\w+)</span>',
        'datetime_key' : {
            'date' : 'date',
            'time' : 'time'
        },
        'time_format' : '%Y.%m.%d %H:%M',
        'order' : 'asc'
    },
    '롯데택배' : {
        'url' : 'https://www.lotteglogis.com/mobile/reservation/tracking/linkView?InvNo={track_no}',
        'type' : 'html',
        'regex_info' : r'<th scope=\"row\">발송지</th>\s+<td>(?P<from>.+)</td>\s+</tr>\s+<tr>\s+<th scope=\"row\">도착지</th>\s+<td>(?P<to>.+)</td>\s+</tr>\s+<tr>\s+<th scope=\"row\">배달결과</th>\s+<td>(?P<status>.+)</td>',
        'regex_tracking' : r'<tr>\s+<td>(?P<tracking_status>[\w\s]+)</td>\s+<td>\s+(?P<date>[\w\-]{10})&nbsp;(?P<time>[\d\:]{5})\s+</td>\s+<td>\s+(?P<tracking_location>.+)\s+</td>\s+<td class=\"left01\">',
        'datetime_key' : {
            'date' : 'date',
            'time' : 'time'
        },
        'time_format' : '%Y-%m-%d %H:%M',
        'order' : 'desc'
    },
    '로젠택배' : {
        'url' : 'https://www.ilogen.com/m/personal/trace/{track_no}',
        'type' : 'html',
        'regex_info' : r'<th>보내시는 분</th>\s+<td>(?P<from>.+)</td>\s+</tr>\s+<tr>\s+<th>받으시는 분</th>\s+<td>(?P<to>.+)</td>\s+</tr>\s+<tr>\s+<th>상품명</th>\s+<td>(?P<item_name>.+)</td>[\W\S]+<th>최종처리시간</th>\s+<td>(?P<date>[\d\.]{10})\s+(?P<time>[\d\:]{5})\s+(?P<status>.+)</td>',
        'regex_tracking' : r'<tr>\s+<td>(?P<date>[\d\.]{10})\s+(?P<time>[\d\:]{5})</td>\s+<td>\s+(?P<tracking_status>.+)\s+</td>\s+<td>[\w\<\>\=\"\#\/\:\-\s]+?</tr>\s+</tbody>\s+</table>[\W\S]+?<th>최종처리 사업장</th>\s+<td>(?P<tracking_location>.+)</td>',
        'datetime_key' : {
            'date' : 'date',
            'time' : 'time'
        },
        'time_format' : '%Y.%m.%d %H:%M',
        'order' : 'asc'
    }
}


class ModuleBasic(PluginModuleBase):
    def __init__(self, P):
        super(ModuleBasic, self).__init__(P, name='basic', first_menu='setting', scheduler_desc="택배 발송 알리미")
        self.db_default = {
            f'db_version' : '1.2',
            f'{self.name}_auto_start': 'False',
            f'{self.name}_interval': '1',
            f'{self.name}_db_delete_day': '7',
            f'{self.name}_db_auto_delete': 'False',
            f'{P.package_name}_item_last_list_option': '',
            f'notify_mode': 'always',
            f'use_delivery_tracking_alarm': 'True',
            f'use_site_대한통운' : 'True',
            f'use_site_경동택배' : 'True',
            f'use_site_한진택배' : 'True',
            f'use_site_우체국택배' : 'True',
            f'use_site_롯데택배' : 'True',
            f'use_site_로젠택배' : 'True',
            f'tracking_no_대한통운' : '',
            f'tracking_no_경동택배' : '',
            f'tracking_no_한진택배' : '',
            f'tracking_no_우체국택배' : '',
            f'tracking_no_롯데택배' : '',
            f'tracking_no_로젠택배' : '',
            'alarm_message_template' : '',
            'alarm_message_template_start' : '',
            'alarm_message_template_end' : ''
        }
        self.web_list_model = ModelItem
    def process_menu(self, sub, req):
        arg = P.ModelSetting.to_dict()
        if sub == 'setting':
            arg['is_include'] = F.scheduler.is_include(
                self.get_scheduler_name())
            arg['is_running'] = F.scheduler.is_running(
                self.get_scheduler_name())
        if sub == 'list':
            arg = self.web_list_model.get_list()
        return render_template(f'{P.package_name}_{self.name}_{sub}.html', arg=arg, site_map=site_map)
    def process_command(self, command, arg1, arg2, arg3, req):
        ret = {'ret': 'success'}
        if command == 'test':
            ret['status'] = 'warn'
            ret['title'] = '테스트'
            ret['data'] = '테스트 내용'
        elif command == 'rename':
            id = arg1
            new_name = arg2
            self.web_list_model.update({'id':id, 'title':new_name})
        return jsonify(ret)

    def scheduler_function(self):
        self.scrap_items()
    
    
    def scrap_items(self):
        try:
            ret = {
                'status': 'success',
                'data': []
            }
            sites = [key.split('_')[-1] for key in list(self.db_default.keys()) if key.startswith('use_site_')]
            use_delivery_sites = [key.split('_')[-1] for key in sites if P.ModelSetting.get(f'use_site_{key}') == 'True']

            for site_name in use_delivery_sites:
                try:
                    if site_name not in site_map:
                        continue
                    
                    track_nos = ModelItem.get_track_no(site_name).replace(' ','').split(',')
                    if not track_nos[0]:
                        continue
                    
                    for track_no in track_nos:
                        try:
                            if 'summary' in site_map[site_name]:
                                info, tracking = self.process_with_summary_tracking(site_name, track_no)
                            else:
                                info, tracking = self.process_without_summary_tracking(site_name, track_no)

                            if info is None or tracking is None:
                                continue

                            if 'item_name' in info or 'item_name' in tracking:
                                item_name = info['item_name'] if 'item_name' in info else tracking['item_name']
                            else:
                                item_name = track_no
                            if item_name.strip() == '':
                                item_name = track_no

                            update_data = {
                                'site_name': site_name,
                                'title': item_name,
                                'track_no': track_no,
                                'status': tracking['tracking_status'] if 'tracking_status' in tracking else info['status'],
                                'datetime': info['datetime'] if 'datetime' in info else tracking['datetime'],
                                'tracking_location': tracking['tracking_location'] if 'tracking_location' in tracking else ''
                            }
                            update_result = self.web_list_model.update(update_data)
                            if 'code' in update_result:
                                self.process_discord_data(update_data, update_result['code'])
                        except Exception as e:
                            P.logger.error(f'택배 추적 중 오류 발생 - {site_name} / {track_no}: {str(e)}')
                            P.logger.error(traceback.format_exc())
                except Exception as e:
                    P.logger.error(f'사이트 처리 중 오류 발생 - {site_name}: {str(e)}')
                    P.logger.error(traceback.format_exc())
        except Exception as e:
            P.logger.error(f'전체 스크래핑 중 오류 발생: {str(e)}')
            P.logger.error(traceback.format_exc())

    def process_with_summary_tracking(self, site_name, track_no):
        try:
            scraper = cloudscraper.create_scraper()
            
            summary_info = self.get_summary_info(scraper, site_name, track_no)
            tracking_info = self.get_tracking_info(scraper, site_name, track_no)
            
            return summary_info, tracking_info
        except Exception as e:
            P.logger.error(f'Summary/Tracking 처리 중 오류 발생 - {site_name} / {track_no}: {str(e)}')
            P.logger.error(traceback.format_exc())
            return None, None

    def process_without_summary_tracking(self, site_name, track_no):
        try:
            scraper = cloudscraper.create_scraper()
            site_url = site_map[site_name]['url']
            
            response = scraper.get(site_url.format(track_no=track_no))
            response = response.text
            
            info = None
            tracking = None

            if 'regex_info' in site_map[site_name]:
                try:
                    info = re.search(site_map[site_name]['regex_info'], response)
                    if info:
                        info = info.groupdict()
                except Exception as e:
                    P.logger.error(f'정규식(info) 처리 중 오류 발생: {str(e)}')
                    
            if 'regex_tracking' in site_map[site_name]:
                try:
                    matches = list(re.finditer(site_map[site_name]['regex_tracking'], response))
                    if matches:
                        if site_map[site_name]['order'] == 'desc':
                            tracking = matches[0].groupdict()
                        else:
                            tracking = matches[-1].groupdict()
                except Exception as e:
                    P.logger.error(f'정규식(tracking) 처리 중 오류 발생: {str(e)}')

            if info or tracking:
                self.process_datetime(site_name, info, tracking)
                if tracking and 'tracking_location' in tracking:
                    tracking['tracking_location'] = tracking['tracking_location'].strip()
                    tracking['tracking_location'] = re.sub(r'<[^>]*>', '', tracking['tracking_location'])

            return info, tracking
        except Exception as e:
            P.logger.error(f'택배 추적 처리 중 오류 발생 - {site_name} / {track_no}: {str(e)}')
            P.logger.error(traceback.format_exc())
            return None, None

    def process_datetime(self, site_name, info, tracking):
        try:
            if 'datetime_key' in site_map[site_name]:
                datetime_key = site_map[site_name]['datetime_key']
                if info and datetime_key['date'] in info and datetime_key['time'] in info:
                    info['datetime'] = info[datetime_key['date']] + ' ' + info[datetime_key['time']]
                elif tracking and datetime_key['date'] in tracking and datetime_key['time'] in tracking:
                    tracking['datetime'] = tracking[datetime_key['date']] + ' ' + tracking[datetime_key['time']]

            if 'time_format' in site_map[site_name]:
                if info and 'datetime' in info:
                    try:
                        info['datetime'] = datetime.strptime(info['datetime'], site_map[site_name]['time_format'])
                    except:
                        info['datetime'] = datetime.strptime(info['datetime'].split('.')[0], '%Y-%m-%d %H:%M')
                if tracking and 'datetime' in tracking:
                    try:
                        tracking['datetime'] = datetime.strptime(tracking['datetime'], site_map[site_name]['time_format'])
                    except:
                        tracking['datetime'] = datetime.strptime(tracking['datetime'].split('.')[0], '%Y-%m-%d %H:%M')
        except Exception as e:
            P.logger.error(f'날짜/시간 처리 중 오류 발생: {str(e)}')
            P.logger.error(traceback.format_exc())

    def get_summary_info(self, scraper, site_name, track_no):
        site_config = site_map[site_name]['summary']
        method = site_config.get('method', 'get')
        
        if method == 'get':
            response = scraper.get(site_config['url'].format(track_no=track_no))
        else:
            req_data = json.dumps(site_config['data'])
            req_data = req_data.replace('{track_no}', track_no)
            req_data = json.loads(req_data)
            response = scraper.post(site_config['url'], data=req_data)
        response_data = response.json()
        
        if 'result_key' in site_config:
            info = {}
            for key, value in site_config['result_key'].items():
                if '.' in key:
                    key_split = key.split('.')
                    info[value] = response_data[key_split[0]][key_split[1]]
                else:
                    info[value] = response_data[key]
                if value == 'datetime':
                    info['datetime'] = info['datetime'].split('.')[0]
            return info
        return response_data

    def get_tracking_info(self, scraper, site_name, track_no):
        site_config = site_map[site_name]['tracking']
        method = site_config.get('method', 'get')
        
        if method == 'get':
            response = scraper.get(site_config['url'].format(track_no=track_no))
        else:
            req_data = json.dumps(site_config['data'])
            req_data = req_data.replace('{track_no}', track_no)
            req_data = json.loads(req_data)
            response = scraper.post(site_config['url'], data=req_data)
        response_data = response.json()
        
        tracking = self.process_tracking_response(site_name, response_data)
        return tracking

    def process_tracking_response(self, site_name, response_data):
        site_config = site_map[site_name]['tracking']
        tracking = {}
        
        if 'result_key' in site_config:
            for key, value in site_config['result_key'].items():
                if '.' in key:
                    key_split = key.split('.')
                    tracking = response_data[key_split[0]][key_split[1]][-1] if len(response_data[key_split[0]][key_split[1]]) > 0 else {}
                else:
                    tracking = response_data[key][-1] if len(response_data[key]) > 0 else {}
        
        if tracking is None:
            tracking = {}
            
        if 'datetime_key' in site_config:
            datetime_key = site_config['datetime_key']
            if type(datetime_key) == str:
                if datetime_key in tracking:
                    tracking['datetime'] = tracking[datetime_key].split('.')[0]
            elif type(datetime_key) == dict:
                if datetime_key['date'] in tracking and datetime_key['time'] in tracking:
                    tracking['datetime'] = tracking[datetime_key['date']] + ' ' + tracking[datetime_key['time']].split('.')[0]
        
        if 'status_key' in site_config:
            if site_config['status_key'] in tracking:
                tracking['tracking_status'] = tracking[site_config['status_key']]
            else:
                tracking['tracking_status'] = tracking.get('tracking_status')
        else:
            tracking['tracking_status'] = tracking.get('tracking_status')

        if 'tracking_location_key' in site_config:
            if site_config['tracking_location_key'] in tracking:
                tracking['tracking_location'] = tracking[site_config['tracking_location_key']]
            else:
                tracking['tracking_location'] = tracking.get('tracking_location', '')
        else:
            tracking['tracking_location'] = tracking.get('tracking_location', '')
        
        if 'tracking_location' in tracking and tracking['tracking_location']:
            # html 태그 제거
            tracking['tracking_location'] = tracking['tracking_location'].strip()
            tracking['tracking_location'] = re.sub(r'<[^>]*>', '', tracking['tracking_location'])

        return tracking

    def process_discord_data(self, update_data, update_result):
        if P.ModelSetting.get_bool('use_delivery_tracking_alarm') is False or update_result == 'skip':
            return
        msg = ''

        if update_result == 'remove':
            msg = P.ModelSetting.get('alarm_message_template_end')
            if msg == None or msg.strip() == '':
                msg = '[추적 완료] '
                msg += '배송이 완료되었습니다.'
                msg += f"\n{update_data['title']} - {update_data['track_no']} - {update_data['status']} - {update_data['datetime']} - {update_data['tracking_location']}"
            else:
                msg = msg.format(**update_data)
        elif update_result == 'insert':
            msg = P.ModelSetting.get('alarm_message_template_start')
            if msg == None or msg.strip() == '':
                msg = '[추적 시작] '
                msg += '배송 추적이 등록되었습니다.'
                msg += f"\n{update_data['title']} - {update_data['track_no']} - {update_data['status']} - {update_data['datetime']} - {update_data['tracking_location']}"
            else:
                msg = msg.format(**update_data)
        elif update_result == 'update':
            msg = P.ModelSetting.get('alarm_message_template')
            if msg == None or msg.strip() == '':
                msg = '[상태 변경] '
                msg += '배송 상태가 변경되었습니다.'
                msg += f"\n{update_data['title']} - {update_data['track_no']} - {update_data['status']} - {update_data['datetime']} - {update_data['tracking_location']}"
            else:
                msg = msg.format(**update_data)
        # msg에서 <strong> 태그를 *로 변경
        msg = re.sub(r'<strong>(.*?)</strong>', r'*\1*', msg)
        ToolNotify.send_message(msg,message_id = f'bot_delivery_tracking_alarm')
