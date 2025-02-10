import sys, cv2
import numpy as np
from mtcnn import MTCNN
import random

file_data = sys.stdin.buffer.read()
nparr = np.frombuffer(file_data, np.uint8)
image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
detector = MTCNN()
faces = detector.detect_faces(image)

if not faces:
    print("SUBPROCESS_MAGA_HAT: NO_FACES")
    sys.exit(0)

for face in faces:
    face_box = face['box']
    x, y, w, h = face_box

    drawing_width = w // 15
    line_end_x = x + w

    circle_radius = w // 3
    half_circle_radius = circle_radius // 2
    circle_center_x = line_end_x - circle_radius - half_circle_radius
    
    line_drawing_steps = drawing_width

    circle_drawing_steps = drawing_width

    num_fill_lines = 20

    y_offset_max = w // 50

    for i in range(x - half_circle_radius, line_end_x - half_circle_radius, line_drawing_steps):
        y_offset = random.randint(-y_offset_max, y_offset_max)
        cv2.line(image, (i, y + y_offset), (i + line_drawing_steps, y + y_offset), (0, 0, 255), drawing_width)

    for angle in range(0, 180, circle_drawing_steps):
        rad = np.deg2rad(angle)
        start_x = circle_center_x + int(circle_radius * np.cos(rad))
        start_y = y - int(circle_radius * np.sin(rad))
        end_x = circle_center_x + int(circle_radius * np.cos(rad + np.deg2rad(circle_drawing_steps)))
        end_y = y - int(circle_radius * np.sin(rad + np.deg2rad(circle_drawing_steps)))

        cv2.line(image, (start_x, start_y), (end_x, end_y), (0, 0, 255), drawing_width)

    for _ in range(num_fill_lines):
        start_x = random.randint(circle_center_x - circle_radius, circle_center_x + circle_radius)
        start_y = y  
        angle_offset = random.uniform(-0.3, 0.3)
        rad = np.deg2rad(90 + angle_offset * 180)
        end_x = circle_center_x + int(circle_radius * np.cos(rad))
        end_y = y - int(circle_radius * np.sin(rad))

        cv2.line(image, (start_x, start_y), (end_x, end_y), (0, 0, 255), drawing_width)

_, buffer = cv2.imencode('.jpg', image)
sys.stdout.buffer.write(buffer)
