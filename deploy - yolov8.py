from ultralytics import YOLO
import cv2
import numpy as np

# load yolov8 model  加载yolov8模型
model = YOLO('yolov8n.pt')
#load video
video_path = './test.mp4'
cap = cv2.VideoCapture(video_path)
ret = True
# read frames  从视频读取帧
while ret:
    ret, frame = cap.read()


    if ret:
        # detect objects  应用对象检测物体
        # track objects  追踪对象
        results = model.track(frame, persist=True)

        # plot results  绘制结果
        frame_ = results[0].plot()

        # visualize  可视化
        cv2.imshow('frame', frame_)
        if cv2.waitKey(25) & 0xFF == ord('q'):
            break