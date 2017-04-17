import cv2
import numpy as np
import cozmo
import asyncio
import random
import time

'''
@class RedLightGreenLight
Play Red Light Green Light with two players and Cozmo as the judge.
@author - Wizards of Coz
'''

class RedLightGreenLight(WOC):    
    def __init__(self):
        WOC.__init__(self)
        self.light = True   #true = green; false = red
        self.thresh = 100
        self.timeout = None
        self.previous_frame = None
        self.current_frame = None
        cv2.namedWindow('Diff')
        cv2.createTrackbar('thresh', 'Diff', 100, 255, self.update_values)
        cozmo.connect(self.run)

    def update_values(self, x):             
        self.thresh = cv2.getTrackbarPos('thresh', 'Diff')

    def look_for_movement(self, img1, img2):
        movement = False
        count1 = 0
        count2 = 0
        rows, cols = img1.shape
        dim = rows*cols*255/100
        for i in range (0, rows):
            for j in range (0, cols):
                count1 += img1[i,j]
                count2 += img2[i,j]
        count1 /= dim
        count2 /= dim
        if count1 > 0:
            self.players[0].set_lights(cozmo.lights.red_light.flash())
            self.robot.set_backpack_lights_off()
            movement = True
        if count2 > 0:
            self.players[1].set_lights(cozmo.lights.red_light.flash())
            self.robot.set_backpack_lights_off()
            movement = True
        return movement

    async def start_game(self):
        while True:
            self.timeout = cozmo.util.Timeout(random.randrange(1,5))
            while self.timeout.is_timed_out is False:
                await asyncio.sleep(0)
            self.light = not self.light
            if self.light is True:
                self.robot.remove_event_handler(cozmo.world.EvtNewCameraImage, self.event_handler)
                self.previous_frame = None
                self.current_frame = None
                self.robot.say_text("green light", duration_scalar=1.2, voice_pitch=0, in_parallel=True)
                self.players[0].set_lights(cozmo.lights.green_light)
                self.players[1].set_lights(cozmo.lights.green_light)
                self.robot.set_all_backpack_lights(cozmo.lights.green_light)
            else:
                self.robot.say_text("red light", duration_scalar=1.2, voice_pitch=0, in_parallel=True)
                self.players[0].set_lights(cozmo.lights.red_light)
                self.players[1].set_lights(cozmo.lights.red_light)
                self.robot.set_all_backpack_lights(cozmo.lights.red_light)
            await self.robot.turn_in_place(cozmo.util.Angle(degrees=180), in_parallel=True).wait_for_completed()
            if self.light is False:
                self.event_handler = self.robot.add_event_handler(cozmo.world.EvtNewCameraImage, self.on_new_camera_image)

    async def on_new_camera_image(self, event, *, image:cozmo.world.CameraImage, **kw):
        self.previous_frame = self.current_frame
        self.current_frame = np.array(image.raw_image)
        gray = cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2GRAY)
        self.current_frame = cv2.GaussianBlur(gray, (5, 5), 0)
        if self.previous_frame is not None:
            diff = cv2.subtract(self.current_frame, self.previous_frame)
            _, thresh = cv2.threshold(diff, self.thresh, 255, cv2.THRESH_BINARY)
            h, w = thresh.shape[:2]
            h = int(h)
            w = int(w/2)
            cv2.line(thresh, (w,0), (w,h), (255,0,0), 1)
            img1 = thresh[0:h, 0:w]
            img2 = thresh[0:h, w:2*w]
            if self.look_for_movement(img1, img2) is True:
                await self.robot.say_text("go back", duration_scalar=1.2).wait_for_completed()
                time.sleep(2)
                self.timeout = cozmo.util.Timeout(0)
            cv2.imshow('Diff', thresh)
            k = cv2.waitKey(10)
            if k == 27:
                exit()

    async def on_tap(self, event, *, obj, tap_count, tap_duration, **kw): 
        if self.light is True:
            self.timeout = cozmo.util.Timeout(20)
            if obj is self.players[0]:
                self.players[0].set_lights(cozmo.lights.blue_light.flash())
                self.players[1].set_lights(cozmo.lights.red_light)
            elif obj is self.players[1]:
                self.players[1].set_lights(cozmo.lights.blue_light.flash())
                self.players[0].set_lights(cozmo.lights.red_light)
            self.robot.set_all_backpack_lights(cozmo.lights.white_light)
            await self.robot.turn_in_place(cozmo.util.Angle(degrees=180)).wait_for_completed()
            await self.robot.play_anim_trigger(cozmo.anim.Triggers.ReactToBlockPickupSuccess).wait_for_completed()
            await self.robot.say_text("you win", duration_scalar=1.1).wait_for_completed()
            time.sleep(2)
            self.robot.set_backpack_lights_off()
            self.players[0].set_lights_off()
            self.players[1].set_lights_off()
            exit()

    async def run(self, conn):
        asyncio.set_event_loop(conn._loop)
        self.robot = await conn.wait_for_robot()
        self.robot.camera.image_stream_enabled = True
        self.event_handler = self.robot.add_event_handler(cozmo.objects.EvtObjectTapped, self.on_tap)
        self.robot.set_robot_volume(1)
        self.robot.set_idle_animation(cozmo.anim.Triggers.Count)
        await self.robot.set_head_angle(cozmo.util.Angle(degrees=0)).wait_for_completed()
        await self.robot.set_lift_height(0).wait_for_completed()
        try:
            self.players = await self.robot.world.wait_until_observe_num_objects(num=2, object_type=cozmo.objects.LightCube, timeout=60)
        except asyncio.TimeoutError:
            print("Cubes not found")
            exit()
        self.players[0].set_lights(cozmo.lights.blue_light)
        self.players[1].set_lights(cozmo.lights.blue_light)
        self.robot.set_all_backpack_lights(cozmo.lights.blue_light)
        await self.robot.say_text("1, 2, 3, green light", duration_scalar=1).wait_for_completed()
        self.players[0].set_lights(cozmo.lights.green_light)
        self.players[1].set_lights(cozmo.lights.green_light)
        self.robot.set_all_backpack_lights(cozmo.lights.green_light)
        await self.start_game()

if __name__ == '__main__':
    RedLightGreenLight()
