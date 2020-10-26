#getDCDataFromYesterday
from matplotlib.pyplot import xticks
import pandas as pd
from datetime import datetime, date, timedelta
import json
import matplotlib.pyplot as plt
import math
import boto3
from boto3.dynamodb.conditions import Key, Attr
import numpy as np
from pandas.core.frame import DataFrame
import os

#Get the service resource.
dynamodb = boto3.resource('dynamodb')
location = os.environ['LOCATION']
table_name = f'Top_50_Trends_{location}'
table = dynamodb.Table(table_name)
s3 = boto3.resource('s3')
bucket_name = "pythonapicpt3"


#Get date for reference
today = date.today()
today_str = today.strftime("%m-%d-%Y")
start_time = datetime.strptime(f'{today_str} 00:00', '%m-%d-%Y %H:%M')

def make_combo_graph (all_data_frame, frame_trends) :

    x = all_data_frame['Date']
    y = all_data_frame['Tweet Volume']
    
    color_numbers = []
    for i in all_data_frame['Trend'] : 
        if(i == frame_trends[0]) :
            color_numbers.append(0)
        if(i == frame_trends[1]) :
            color_numbers.append(1)
        if(i == frame_trends[2]) :
            color_numbers.append(2)
        if(i == frame_trends[3]) :
            color_numbers.append(3)
        if(i == frame_trends[4]) :
            color_numbers.append(4)

    title = f'Current Top 5 Trends - {location}'

    plt.figure(figsize = (12,6))
    plt.scatter(x,y,c=color_numbers, cmap='plasma')
    plt.title(title, fontsize=20)
    plt.ylabel('# of Tweets per 24 hr (100k)', fontsize=12)
    plt.xlabel('Date & Hour', fontsize=12) 
    marker_color = plt.cm.get_cmap('plasma', 5)

    legend_aliases = [
        plt.scatter([], [], marker='o', label=frame_trends[0], edgecolors = marker_color(0), color=marker_color(0)),
        plt.scatter([], [], marker='o', label=frame_trends[1], edgecolors = marker_color(1), color=marker_color(1)),
        plt.scatter([], [], marker='o', label=frame_trends[2], edgecolors = marker_color(2), color=marker_color(2)),
        plt.scatter([], [], marker='o', label=frame_trends[3], edgecolors = marker_color(3), color=marker_color(3)),
        plt.scatter([], [], marker='o', label=frame_trends[4], edgecolors = marker_color(4), color=marker_color(4))
    ]
    plt.legend(handles=legend_aliases, loc='upper center')
        
    save_picture_name = f'{location}_Current_All.png'
    lambda_path = '/tmp/' + save_picture_name
    bucket_path = f'charts/{location}_Trends/{save_picture_name}'
    plt.savefig(lambda_path)

    s3.Bucket(bucket_name).upload_file(Filename=lambda_path,Key=bucket_path)

    plt.close()

def make_solo_graph (data_frame, trend_name, frame_trends, index) :

    x = data_frame['Date']
    y = data_frame['Tweet Volume']
    title = f'{trend_name} Tweet Volume - Current'

    color_numbers = []
    marker_color = plt.cm.get_cmap('plasma', 5)
    for i in data_frame['Trend'] : 
        if(i == frame_trends[0]) :
            color_numbers.append(marker_color(0))
        if(i == frame_trends[1]) :
            color_numbers.append(marker_color(1))
        if(i == frame_trends[2]) :
            color_numbers.append(marker_color(2))
        if(i == frame_trends[3]) :
            color_numbers.append(marker_color(3))
        if(i == frame_trends[4]) :
            color_numbers.append(marker_color(4))

    plt.figure(figsize = (12,6))
    plt.scatter(x,y,c=color_numbers, cmap='plasma')
    plt.title(title, fontsize=20)
    plt.ylabel('# of Tweets per 24 hr (100k)', fontsize=12)
    plt.xlabel('Date & Hour', fontsize=12) 
    
    save_picture_name = f'{location}_Current_{index}.png'
    lambda_path = '/tmp/' + save_picture_name
    bucket_path = f'charts/{location}_Trends/{save_picture_name}'
    plt.savefig(lambda_path)

    s3.Bucket(bucket_name).upload_file(Filename=lambda_path,Key=bucket_path)

    plt.close()

def lambda_handler(event, context) :

    #get data
    response = table.scan(FilterExpression=Attr('TimeStamp').begins_with(today_str))
    table_data = response['Items']
    
    while 'LastEvaluatedKey' in response :
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'],FilterExpression=Attr('TimeStamp').begins_with(today_str))
        table_data.extend(response['Items'])
        
    trend_names = {}
    
    for i in table_data :
        if i['Trend_Name'] not in trend_names :
            trend_names.update({i['Trend_Name'] : {'max' : 0, 'data' : [], 'latest_time' : start_time}})
            if i['Tweet_Volume'] != 'None' : 
                trend_names[i['Trend_Name']].update({'max' : int(i['Tweet_Volume'])})
                
        elif i['Tweet_Volume'] != 'None' :
            if int(i['Tweet_Volume']) > trend_names[i['Trend_Name']]['max'] :
                trend_names[i['Trend_Name']].update({'max' : int(i['Tweet_Volume'])})
            
    
    data_time_counter = 0
    for i in table_data:
        data_time = datetime.strptime(i['TimeStamp'], '%m-%d-%Y %I:%M %p')
        if data_time > trend_names[i['Trend_Name']]['latest_time'] :
            trend_names[i['Trend_Name']].update({'latest_time' : data_time})
        if i['Tweet_Volume'] == 'None' :
            trend_names[i['Trend_Name']]['data'].append({'TimeStamp' : data_time, 'Tweet_Volume' : 0})    
        else:
            trend_names[i['Trend_Name']]['data'].append({'TimeStamp' : data_time, 'Tweet_Volume' : i['Tweet_Volume']})
    
    sort_trends_list = sorted(trend_names.items(), key=lambda x: x[1]['latest_time'], reverse=True)
    sort_trends_list = sort_trends_list[0:50]
    
    sort_trends_list.sort(key=lambda x: x[1]['max'], reverse=True)
    top_trends_list = sort_trends_list[0:5]
    top_trends_dict = {}

    for i in top_trends_list :
        top_trends_dict[i[0]] = i[1]
        
    #data_json = json.dumps(top_trends_dict)
    pd_data = DataFrame.from_dict(top_trends_dict)

    trends = list(top_trends_dict)

    all_data_list = []
    single_data_list = [[],[],[],[],[]]
    scale_number = 100000

    index = 0
    for trend in trends:
        for data in pd_data[trend]['data'] :
            #data_time = datetime.strptime(data['TimeStamp'], '%m-%d-%Y %I:%M %p')
            data_time = data['TimeStamp']
            data_volume = float(data['Tweet_Volume']) / scale_number
            all_data_list.append([trend,data_time,data_volume])
            single_data_list[index].append([trend,data_time,data_volume])
        index += 1


    all_data_frame = DataFrame(all_data_list,columns=['Trend','Date','Tweet Volume'])
    single_data_frame = []

    for i in single_data_list :
        single_data_frame.append(DataFrame(i,columns=['Trend','Date','Tweet Volume']))

    make_combo_graph(all_data_frame, trends)

    index = 1
    for i in single_data_frame :
        make_solo_graph(i,i['Trend'][0], trends,index)
        index += 1