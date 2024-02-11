import time
import win32api
import win32con

start_time = None
move_flag = True
caps_lock_state = False

while True:
    # 检查大小写键是否被按下
    if win32api.GetAsyncKeyState(win32con.VK_CAPITAL) < 0:
        # 如果按下，切换大小写键状态
        caps_lock_state = not caps_lock_state
        # 加入暂停，防止频繁检测到同一次按下键
        time.sleep(0.1)

    # 检查鼠标左键状态
    state_left = win32api.GetAsyncKeyState(win32con.VK_LBUTTON)

    # 检查大小写键状态
    state_capslock = win32api.GetAsyncKeyState(win32con.VK_CAPITAL)

    # 如果左键被按下，并且可以移动鼠标，开始移动
    if caps_lock_state and state_left < 0 and move_flag:
        # 如果是第一次按下鼠标左键，记录下时间
        if start_time is None:
            start_time = time.time()

        # 判断是否已经超过一秒
        if time.time() - start_time <= 0.7:
            win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, 0, 2)
            time.sleep(0.01)
        else:
            # 超过start_time后，禁止移动鼠标
            move_flag = False

    else:
        # 鼠标左键未被按下，或者已经超过start_time，重置开始时间，并允许移动鼠标
        if (not move_flag and state_left >= 0) or state_left >= 0:
            start_time = None
            move_flag = True

    #  变量caps_lock_state来保存大小写键的状态，并设置初始状态为关闭。然后在while循环中使用if win32api.GetAsyncKeyState(win32con.VK_CAPITAL) < 0:
    #  判断每次大小写键是否被按下，如果按下就切换caps_lock_state的状态。然后在检查鼠标左键的if条件中加入caps_lock_state来检查是否可以移动鼠标。