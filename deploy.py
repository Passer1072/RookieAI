### importing required libraries
import gc
from json.encoder import INFINITY
import torch
import os
import cv2
from time import time, sleep
import win32api, win32con
import pyautogui
import numpy as np
import mss
from math import sqrt
import PySimpleGUI as sg
import serial
import win32con
import json
import keyboard
import sys
import random


frame_counter = 0
start_time = time()

triggerType = None

aimbot = True  # 如果 True，则启用瞄准机器人

arduinoMode = False  # Using an arduino mouse spoof?

start_moving = False

screenShotWidth = 350  # 检测盒宽度 建议：350
screenShotHeight = 350  # 检测盒高度 建议：350

headshot_mode = False  # 如果 True，则将目标拉向头部

no_headshot_multiplier = 0.2  # 如果爆头模式为 false，则数量乘数目标会增加
headshot_multiplier = 0.35  # 如果爆头模式为真，则数量乘数目标会增加

detection_threshold = 0.65  # 切断敌人瞄准的确定性百分比(置信度)0.65

lockKey = 0x2  # 0x14大小写 0x05下侧键 0x2右键 0x1左键


sct = mss.mss()

layout = [
    [
        sg.Text("模型选择"),
        sg.In(size=(25, 1), enable_events=True, key="-FOLDER-"),
        sg.FolderBrowse(),
    ],
    [
        [sg.Listbox(
            values=[], enable_events=True, size=(40, 20), key="-FILE LIST-"
        )],
        [sg.Text('游戏窗口', size=(15, 1)), sg.Combo(["Apex Legends", "任务管理器"], key="gw1")],
        [sg.Text('自瞄范围', size=(15, 1)), sg.InputText("100", key="ld1")],
        [sg.Text('自瞄速度', size=(15, 1)), sg.InputText("0.4", key="ls1")],
        [sg.Button('保存设置'), sg.Button('开始'), sg.Button('退出')]
    ],
]


### -------------------------------------- function to run detection ---------------------------------------------------------
def configSettings():
    global aimbot, screenShotWidth, screenShotHeight, detection_threshold, triggerType, test
    # 从文件加载初始配置
    test = 1
    # print(triggerType)
    # print(test)
    with open('config.json', 'r') as f:
        config = json.load(f)
        # 定义窗口的布局
    layout = [[sg.Text("自瞄开关"), sg.Checkbox('', key='aimbot', default=config.get('aimbot'))],
              [sg.Text("检测窗口宽度"), sg.Input(config.get('screenShotWidth'), key='screenShotWidth')],
              [sg.Text("检测窗口高度"), sg.Input(config.get('screenShotHeight'), key='screenShotHeight')],
              [sg.Text("置信度（0~1）"), sg.Input(config.get('detection_threshold'), key='detection_threshold', size=(15, 5))],
              [sg.Text("aimbot触发方式"), sg.Combo(["切换", "按下", "大小写开关+切换", "shitf+按下"], key='triggerType', size=(15, 5))],
              [sg.Text("aimbot触发键"), sg.Input(config.get('lockKey'), key='lockKey', size=(5, 5))],
              [sg.Button('保存配置文件'), sg.Button('加载配置文件'), sg.Button('应用'), sg.Button('以默认值继续'),
               sg.Button('以自定义值继续')]]
    # 创建窗口
    window = sg.Window("参数设置", layout)
    # 处理事件
    while True:
        event, values = window.read()
        if event == "保存配置文件":
            with open('config.json', 'w') as f:
                json.dump(values, f, indent=4)
            sg.popup('配置已保存')
        elif event == "应用":  # 新的 'Apply' 事件处理
            # 更新全局变量
            aimbot = values.get('aimbot')
            screenShotWidth = int(values.get('screenShotWidth'))
            screenShotHeight = int(values.get('screenShotHeight'))
            detection_threshold = float(values.get('detection_threshold'))
            sg.popup('配置已应用')
        elif event == "加载配置文件":
            with open('config.json', 'r') as f:
                config = json.load(f)
            window['aimbot'].update(config.get('aimbot'))
            window['screenShotWidth'].update(config.get('screenShotWidth'))
            window['screenShotHeight'].update(config.get('screenShotHeight'))
            window['detection_threshold'].update(config.get('detection_threshold'))
            sg.popup('配置已加载')
        elif event == "以默认值继续":
            break
        elif event == "以自定义值继续":
            aimbot = values.get('aimbot')
            screenShotWidth = int(values.get('screenShotWidth'))
            screenShotHeight = int(values.get('screenShotHeight'))
            detection_threshold = float(values.get('detection_threshold'))
            triggerType = str(values['triggerType'])  # 获取用户输入的 triggerType
            lockKey = str(values['lockKey'])  # 获取用户输入的 lockKey
            print("瞄准触发方式为：", triggerType)
            print("热键设置为：", lockKey)
            # print(type(lockKey))
            sg.popup('配置已应用，即将启动')
            break
        elif event == sg.WINDOW_CLOSED:
            window.close()
            sys.exit(0)  # 结束整个程序
    # 关闭窗口
    window.close()
    # print(triggerType)
    return triggerType, test


def detectx(frame, model):  # 推理部分
    # start_time = time()

    frame = [frame]
    # print(f"[INFO] Detecting. . . ")
    results = model(frame)

    end_time = time()
    # inference_time = end_time - start_time
    # print(f"Inference time: {inference_time} seconds")

    labels, cordinates = results.xyxyn[0][:, -1], results.xyxyn[0][:, :-1]

    return labels, cordinates


def FindPoint(x1, y1, x2,
              y2, x, y):
    if (x1 < x < x2 and
            y1 < y < y2):
        return True
    else:
        return False


### ------------------------------------ to plot the BBox and results --------------------------------------------------------

def plot_boxes(results, frame, area, arduino, lockDistance, lockSpeed, classes, triggerType):
    global frame_counter
    global start_time
    # print(test)
    # print("测试点1", triggerType)

    labels, cord = results
    n = len(labels)
    x_shape, y_shape = frame.shape[1], frame.shape[0]

    best_detection = None

    closest_mouse_dist = INFINITY

    cWidth = area["width"] / 2
    cHeight = area["height"] / 2

    ### looping through to find closest target to mouse 循环查找距离鼠标最近的目标
    for i in range(n):
        row = cord[i]
        if row[4] >= detection_threshold:  ### 检测阈值。 我们将丢弃低于该值的所有内容
            confidence_score = row[4]
            x1, y1, x2, y2 = int(row[0] * x_shape), int(row[1] * y_shape), int(row[2] * x_shape), int(row[3] * y_shape)  ## BBOx coordniates BBOx 坐标

            # 单独赋值画线的终点
            x_line1, y_line1 = x1, y1
            cv2.line(frame, (0, 0), (x_line1, y_line1), (0, 0, 255), 1)  # 画线

            ### 检查鼠标的距离，如果最接近，请选择此
            centerx = x1 - (0.5 * (x1 - x2))
            centery = y1 - (0.5 * (y1 - y2))

            centerx = centerx - cWidth
            centery = centery - cHeight

            dist = sqrt((0 - centerx) ** 2 + (0 - centery) ** 2)

            # 鼠标向最近的目标移动
            if dist < closest_mouse_dist and dist < lockDistance:
                best_detection = row
                closest_mouse_dist = dist

            # 为这个检测画一个边界框
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)  ## BBox

            ## 在边界框上添加置信度标签
            label = f"{confidence_score:.2f}"
            labelSize, baseLine = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
            label_ymin = max(y1, labelSize[1] + 10)
            cv2.rectangle(frame, (x1, label_ymin - labelSize[1] - 10), (x1 + labelSize[0], label_ymin + baseLine - 10),
                          (255, 255, 255), cv2.FILLED)
            cv2.putText(frame, label, (x1, label_ymin - 7), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    # print(triggerType)
    # print("目标：", best_detection)
    if best_detection is not None:
        x1, y1, x2, y2 = int(best_detection[0] * x_shape), int(best_detection[1] * y_shape), int(
            best_detection[2] * x_shape), int(best_detection[3] * y_shape)  ## BBOx coordniates

        box_height = y1 - y2

        if headshot_mode == True:
            headshot_offset = box_height * headshot_multiplier
        else:
            headshot_offset = box_height * no_headshot_multiplier

        centerx = x1 - (0.5 * (x1 - x2))
        centery = y1 - (0.5 * (y1 - y2))

        centerx = centerx - cWidth
        centery = (centery + headshot_offset) - cHeight

        # 触发方式选择=
        # print(type(triggerType))
        # print("测试点2", triggerType)
        # 第一种（使用触发键切换）
        if triggerType == "切换":
            print(101)
            if aimbot == True and win32api.GetKeyState(lockKey) and arduinoMode == False:
                win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, int(centerx * lockSpeed), int(centery * lockSpeed), 0, 0)
            elif aimbot == True and win32api.GetKeyState(lockKey) and arduinoMode == True:
                centerx = centerx - 960
                centery = centery - 540
                arduino.write(((centerx * lockSpeed) + ':' + (centery * lockSpeed) + 'x').encode())
        # 第二种 （使用触发键按下）
        elif triggerType == "按下":
            print(102)
            if aimbot == True and (win32api.GetKeyState(lockKey) & 0x8000) and arduinoMode == False:
                win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, int(centerx * lockSpeed), int(centery * lockSpeed), 0, 0)
            elif aimbot == True and not (win32api.GetKeyState(lockKey) & 0x8000) and arduinoMode == False:
                # 在这里添加停止代码
                pass
            elif aimbot == True and (win32api.GetKeyState(lockKey) & 0x8000) and arduinoMode == True:
                centerx = centerx - 960
                centery = centery - 540
                arduino.write(((centerx * lockSpeed) + ':' + (centery * lockSpeed) + 'x').encode())
        # 第三种 (使用大小写键开关aimbot 按下触发键触发)
        elif triggerType == "大小写开关+切换":
            print(103)
            if aimbot == True and (win32api.GetKeyState(lockKey) & 0x8000) and win32api.GetKeyState(
                    win32con.VK_CAPITAL) & 0x0001 and arduinoMode == False:
                win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, int(centerx * lockSpeed), int(centery * lockSpeed), 0, 0)
            elif aimbot == True and not (win32api.GetKeyState(lockKey) & 0x8000) and win32api.GetKeyState(
                    win32con.VK_CAPITAL) & 0x0001 and arduinoMode == False:
                # 停止代码
                pass
            elif aimbot == True and (win32api.GetKeyState(lockKey) & 0x8000) and win32api.GetKeyState(
                    win32con.VK_CAPITAL) & 0x0001 and arduinoMode == True:
                centerx = centerx - 960
                centery = centery - 540
                arduino.write(((centerx * lockSpeed) + ':' + (centery * lockSpeed) + 'x').encode())
        # 第四种 （当按下shift时同时按下触发键触发）
        elif triggerType == "shitf+按下":
            print(104)
            if aimbot and win32api.GetKeyState(lockKey) & 0x8000:
                # 检查 Shift 键是否按下
                shift_pressed = win32api.GetKeyState(win32con.VK_SHIFT) & 0x8000

                if shift_pressed and not arduinoMode:
                    win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, int(centerx * lockSpeed), int(centery * lockSpeed), 0,
                                         0)
                elif not shift_pressed and not arduinoMode:
                    # 停止代码
                    pass
                elif shift_pressed and arduinoMode:
                    centerx -= 960
                    centery -= 540
                    arduino.write(f"{int(centerx * lockSpeed)}:{int(centery * lockSpeed)}x".encode())
    # print(f"[INFO] Finished extraction, returning frame!")
    # 更新帧计数器
    frame_counter += 1

    # get the frame rate
    end_time = time()
    # 避免被零除
    if end_time - start_time != 0:
        frame_rate = frame_counter / (end_time - start_time)
        # 重置下一秒的frame_counter和start_time
        frame_counter = 0
        start_time = time()
    else:
        frame_rate = 0  # Or assign something that makes sense in your case

    # display the frame rate
    cv2.putText(frame, f"FPS: {frame_rate:.2f}", (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    return frame


### ---------------------------------------------- Main function -----------------------------------------------------
def main(arduino=False, run_loop=False, modelPath=None, gameWindow=None, lockSpeed=None, lockDist=None,  triggerType=None):

    count_time = 0  # 初始化计数器
    print_frequency = 20  # 每处理20帧打印一次

    # 调用函数显示配置设置
    triggerType, test = configSettings()
    if arduino == True:
        arduino = serial.Serial('COM5', 9600, timeout=1)

    print(f"[INFO] Loading model... ")
    ## loading the custom trained model 加载自定义训练模型 yolov5/yolov8-face-main
    model = torch.hub.load('./yolov5', 'custom', source='local', path=modelPath, force_reload=True)

    classes = model.names  ### class names in string format

    if run_loop == True:

        # Selecting the correct game window
        try:
            videoGameWindows = pyautogui.getWindowsWithTitle(gameWindow)
            videoGameWindow = videoGameWindows[0]
        except:
            print("The game window you are trying to select doesn't exist.")
            print("Check variable videoGameWindowTitle (typically on line 36)")
            exit()

        # Select that Window 选择该窗口
        videoGameWindow.activate()

        sctArea = {"mon": 1, "top": videoGameWindow.top + (videoGameWindow.height - screenShotHeight) // 2,
                   "left": ((videoGameWindow.left + videoGameWindow.right) // 2) - (screenShotWidth // 2),
                   "width": screenShotWidth,
                   "height": screenShotHeight}

        cv2.namedWindow("vid", cv2.WINDOW_NORMAL)

        count = 0
        sTime = time()

        print("Program Working!")

        while True:

            img = sct.grab(sctArea)

            img = np.array(img)

            frame = img

            # print(f"[INFO] Working with frame {frame_no} ")
            if (gameWindow == "Halo Infinite"):
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            results = detectx(frame, model=model)

            # 定义开始时间
            start_time = time()
            frame = plot_boxes(results, frame, sctArea, arduino, lockDistance=lockDist, lockSpeed=lockSpeed,
                               classes=classes, triggerType=triggerType)

            # 在你的代码之后定义结束时间
            end_time = time()
            # 计算推理时间
            inference_time = end_time - start_time
            inference_time_ms = inference_time * 1000
            # print(f"Inference time: {inference_time_ms:.2f} ms")

            count_time += 1
            if count_time % print_frequency == 0:  # 每处理print_frequency帧打印一次
                print(f"Inference time: {inference_time_ms:.2f} ms")

            # 在图像上添加推理时间
            cv2.putText(frame, f"Inference time: {inference_time_ms:.2f} ms", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1,
                        (0, 0, 255), 2)
            cv2.imshow("vid", frame)

            if cv2.waitKey(1) and 0xFF == ord('q'):
                break

            if keyboard.is_pressed('home'):
                print(f"[INFO] Exiting. . . ")
                break

            # Forced garbage cleanup every second 每秒强制清理垃圾
            count += 1
            if (time() - sTime) > 1:
                # print("CPS: {}".format(count))
                count = 0
                sTime = time()

                gc.collect(generation=0)

        print(f"[INFO] Cleaning up. . . ")

        ## closing all windows
        exit()


def selectSettings():
    window = sg.Window("基础设置", layout)

    chosenModel = "replaceme.pt"

    while True:
        event, values = window.read()

        # Folder name was filled in, make a list of files in the folder
        if event == "-FOLDER-":
            folder = values["-FOLDER-"]
            try:
                # Get list of files in folder
                file_list = os.listdir(folder)
            except:
                file_list = []

            fnames = [
                f
                for f in file_list
                if os.path.isfile(os.path.join(folder, f))
                   and f.lower().endswith((".pt"))
            ]
            window["-FILE LIST-"].update(fnames)

        elif event == "-FILE LIST-":  # A file was chosen from the listbox
            try:
                filename = os.path.join(
                    values["-FOLDER-"], values["-FILE LIST-"][0]
                )
                chosenModel = filename
            except:
                pass

        elif event == '开始':
            if values['ld1'] != "":
                ld = float(values['ld1'])
            else:
                ld = 100

            if values['gw1'] != "":
                gw = values['gw1']
            else:
                gw = "Counter"

            if values['ls1'] != "":
                ls = float(values['ls1'])
            else:
                ls = 2
            break

        elif event == "退出" or event == sg.WIN_CLOSED:
            window.close()
            exit()

    window.close()

    print("Model Path: ", str(chosenModel))
    print("Lock Distance: ", str(ld))
    print("Lock Speed: ", str(ls))
    print("Game Window: ", str(gw))

    return chosenModel, gw, ld, ls


### -------------------  calling the main function-------------------------------

chosenModel, gw, ld, ls = selectSettings()
main(run_loop=True, modelPath=chosenModel, gameWindow=gw, lockDist=ld, lockSpeed=ls)


