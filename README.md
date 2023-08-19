# visionect-fog

A simple script to get the latest image from Logan Williams' [Fog Today](https://fog.today) and push it to a [Visionect Place & Play 13"](https://www.visionect.com/shop/place-play-13/) e-ink display.

The script does the following:
1. Grab the latest image and timestamp from Fog Today
2. Crop the image a bit and boost the contrast
3. Save the image to file, then push it to the Visionect display

## Usage
1. Configure the display and set up the Visionect Software Suite (VSS), following the [documentation by Visionect](https://docs.visionect.com/index.html).
    - As of August 2023, Visionect's product page suggests that a subscription is needed to use the display; however, I was able to configure the display and run VSS on my local network without a subscription.
    - As VSS needs to be running continuously for the display image to be updated, I'd recommend installing it on a local server or similar.
2. In the device "Status & Settings" page of VSS (after clicking into the device and then clicking "Advanced" at upper right), change the Backend setting to `HTTP - external renderer`.
3. Create a new `.env` file from my sample file: `cp .env-sample .env`
4. Fill out the `.env` file with your VSS server URL, API key, API secret, and device UUID.
    - To get an API key and secret: In VSS, under the "Users" page, click "Add new API key" at lower right.
5. Run the Python script: `python3 update_image.py`. 

I have the script scheduled to run every 10 minutes using cron.

## Links, References, and Credits
- I referenced [newsvision by @elidickinson](https://github.com/elidickinson/newsvision/tree/main) for the basics of pushing images to the Visionect display.
- I used [ChatGPT](https://chat.openai.com) to help me quickly write much of the code.