import matplotlib.pyplot as plt
import PIL.Image
import glob
import cv2
import numpy as np
import numexpr as ne

# local imports below
from houghlanedetect.gaussian import do_gaussian
# from houghlanedetect.canny import do_canny
# from houghlanedetect.hough import do_hough_straightline, do_hough_curve

PLOT_INTERMEDIARY = True # display results of each step
PLOT_RESULTS = True # save final result in result folder

GAUSSIAN_SIZE = 5 # kernel size
CANNY_LOW = 5
CANNY_HIGH = 15
CANNY_ADAPTIVE_THRESH = True # set to true to use median-based threshold instead of fixed values above
ACCUMULATOR_MAX_AREA = 10 # area around maximum to set to 0 in accumulator before looking for next candidate
N_LINES = 2 # number of lanes

# def detect_lane_from_img(orig_img):
#     img = orig_img[:,:,0] # only keep one channel
#     img = img[220:,:]
#
#     # downsample image
#     h,w = img.shape[:2]
#     desired_w = 250
#     small_to_large_image_size_ratio = desired_w/w
#     img = cv2.resize(img,
#                        (0,0), # set fx and fy, not the final size
#                        fx=small_to_large_image_size_ratio,
#                        fy=small_to_large_image_size_ratio,
#                        interpolation=cv2.INTER_LINEAR)
#     blurred_cv = cv2.GaussianBlur(img,ksize=(5,5),sigmaX=3)
#     edges = do_canny(blurred_cv, CANNY_ADAPTIVE_THRESH, low=CANNY_LOW, high=CANNY_HIGH, plot=False)
#
#
#     return edges

GAUSSIAN_SIZE = 5 # kernel size
CANNY_LOW = 8
CANNY_HIGH = 16
DOWNSCALING_FACTOR = 0.3
HORIZON = 220

colors = {
            'white':(255, 255, 255),
            'black':(0,0,0),
            'green':(0, 255, 0),
            'blue':(255,0,0),
            'red':(0,0,255),
            'yellow':(255,255,0)
}

def preprocessing(image):
    # only keep bottom part of image
    img = image[HORIZON:,:]

    # downsample image
    h,w = img.shape[:2]
    #desired_w = 150
    small_to_large_image_size_ratio = DOWNSCALING_FACTOR
    img = cv2.resize(img,
                       (0,0), # set fx and fy, not the final size
                       fx=small_to_large_image_size_ratio,
                       fy=small_to_large_image_size_ratio,
                       interpolation=cv2.INTER_LINEAR)

    blurred = cv2.GaussianBlur(img, (GAUSSIAN_SIZE, GAUSSIAN_SIZE), 0)
    return blurred


def plot_line(a, b, rho, img, opacity=0.8, color='red',downsampling=1):
    y_max, x_max = img.shape[:2]
    #a = a * downsampling
    if downsampling < 1:
        b = (b / downsampling)+HORIZON
    pt1 = (0, int(a * 0 + b))
    pt2 = (x_max, int(a * x_max + b))
    cv2.line(img, pt1, pt2, colors[color], 1, cv2.LINE_AA)
    #print(a, b)
    return img

def is_theta_in_range(theta):
    return (theta < np.deg2rad(-10) and theta > np.deg2rad(-70)) or (theta > np.deg2rad(10) and theta < np.deg2rad(70))

def theta_ranges_from_lane_angle(lane_angle):
    if lane_angle == None:
        return np.deg2rad(np.concatenate((np.arange(-70,-10),np.arange(10,70))))
        # return np.deg2rad(np.arange(-90,90))
    theta_offset = 70
    print('Theta limits:',lane_angle-theta_offset,lane_angle+theta_offset)
    return np.deg2rad(np.concatenate((np.arange(lane_angle-theta_offset,-10),np.arange(10,lane_angle+theta_offset))))

def do_hough_straightline(orig, img, lane_angle, n_lines, max_area, plot=False):
    # Copy edges to the images that will display the results in BGR
    color_edges = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    color_orig = orig
    blank_orig = np.zeros_like(orig)

    # img = img[10:-10][10:-10] # ignore image boundaries
    # print("-------------------------------------")
    max_iterations = 20

    h, w = img.shape
    h_orig, w_orig = orig.shape[:2]
    middle = w / 2
    print("Image center:",middle)
    diag = np.ceil(np.hypot(h, w))
    # print(f"IMG dimensions: {img.shape} max. intensity: {np.max(img)}")

    thetas = theta_ranges_from_lane_angle(lane_angle)
    rhos = np.linspace(-diag, diag, diag * 2.0)

    # print(f"diagonal: {diag}")

    accumulator = np.zeros((np.uint64(2 * diag), len(thetas)), dtype=np.uint64)

    for i in range(0, h):
        for j in range(0, w):
            if img[i, j] > 0:  # if we're on an edge
                rho_calc = ne.evaluate("j * cos(thetas) + i * sin(thetas) + diag")
                for rho_i,rho in enumerate(rho_calc):
                    accumulator[np.uint64(rho_calc[rho_i]), rho_i] += 1  # increment accumulator for this coordinate pair

    n = 1
    iterations = 0

    lane_start = [0,0]
    lane_end = [0,0]
    lane_pos = [0,0]
    lane_side = [0,0]

    while n <= n_lines and iterations < max_iterations:
        # print(iterations)
        # find maximum point in accumulator

        max_index = np.argmax(accumulator)  # 2d index of maximum point in accumulator
        theta_index = np.uint16(max_index % accumulator.shape[1])
        rho_index = np.uint16(max_index / accumulator.shape[1])

        ang = thetas[theta_index]
        rho = rhos[rho_index]

        lane_pos[n-1] = (ang > 0)
        a = -(np.cos(ang) / np.sin(ang))
        b = rho / np.sin(ang)
        lane_start[n-1] = ((h - 1) - b) / a
        lane_end[n-1] = -b / a
        lane_side[n-1] = (lane_start[n-1] < middle)

        print(f"- Lane {n}: Cartesion form (ax+b): {a:.2f} * x + {b:.2f}")
        print(f"- Lane {n}: Theta {np.rad2deg(ang):.2f} - Rho {rho:.2f}")

        if n == 1:
            color_edges =   plot_line(a, b, rho, color_edges, color='green')
            color_orig =    plot_line(a, b, rho, color_orig, color='green', downsampling=DOWNSCALING_FACTOR)
            blank_orig = plot_line(a, b, rho, blank_orig, color='white', downsampling=DOWNSCALING_FACTOR)
            #accumulator = remove_area_around_max(accumulator,max_area,(rho_index,theta_index))
            n += 1
        elif n == 2:
            if      (lane_side[n-1] != lane_side[n-2]) and \
                    ((lane_end[n-1] > lane_end[n-2] and lane_start[n-1] > lane_start[n-2]) \
                or  (lane_end[n-1] < lane_end[n-2] and lane_start[n-1] < lane_start[n-2])):
                lane_color = 'blue'
                color_orig = plot_line(a, b, rho, color_orig, color=lane_color, downsampling=DOWNSCALING_FACTOR)
                blank_orig = plot_line(a, b, rho, blank_orig, color='white', downsampling=DOWNSCALING_FACTOR)
                n += 1
            else:
                lane_color = 'red'
                #accumulator = remove_area_around_max(accumulator,max_area,(rho_index,theta_index))
            color_edges =   plot_line(a, b, rho, color_edges, color=lane_color)

        for i in range(np.int(rho_index - max_area), np.int(rho_index + max_area + 1)):
            try:
                accumulator[i][np.int(theta_index - max_area):np.int(theta_index + max_area)] = 0
            except:
                pass
        prev_ang = ang
        prev_rho = rho

        iterations += 1

    print("Solved in",iterations,"iterations")

    return color_edges, color_orig, blank_orig[HORIZON:,:]


def draw_lanes_from_img(orig_img, lane_angle = None):
    image = orig_img[:, :, 0]
    image_preprocessed = preprocessing(image)
    edges = cv2.Canny(image_preprocessed, CANNY_LOW, CANNY_HIGH, None, 3)
    color_edges, color_orig, blank_orig= do_hough_straightline(image, edges, lane_angle=lane_angle, n_lines=2, max_area=5, plot=False)
    color_edges = cv2.cvtColor(np.float32(color_edges), cv2.COLOR_BGR2RGB)
    return color_edges


def draw_lanes(image_path):
    image = cv2.imread(image_path)
    image_preprocessed = preprocessing(image)
    edges = cv2.Canny(image_preprocessed, CANNY_LOW, CANNY_HIGH, None, 3)
    return do_hough_straightline(image, edges, lane_angle=None, n_lines=2, max_area=5, plot=False)


# for path in glob.iglob('/home/zacefron/Desktop/golfcart-sensorfusion/sensorfusion/cam_data/ir/*.png'):
#     print(path)
#     color_edges, color_orig, blank_orig = draw_lanes(path)
#     #cv2.imshow('orig',orig)
#     cv2.imshow('original',color_orig)
#     cv2.imshow('edges', color_edges)
#     cv2.imshow('binary', blank_orig)
#     k = cv2.waitKey(0) & 0xFF
#     if k == ord('q'):
#         break
