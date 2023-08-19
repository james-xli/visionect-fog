import requests
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from bs4 import BeautifulSoup
from io import BytesIO
import datetime
import os
from dotenv import load_dotenv

def fetch_text_from_url(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    timestamp = soup.find('div', {'id': 'timestamp'}).text.strip()
    return timestamp

def crop_and_upscale_image_with_overlay(image_url, text_url, output_path, left, upper, right, lower, upscale_factor=2):
    # Download the image from the image URL
    response = requests.get(image_url)
    img = Image.open(BytesIO(response.content))
    
    # Crop the image
    cropped_img = img.crop((left, upper, right, lower))
    
    # Calculate the new dimensions for upscale
    new_width = int(cropped_img.width * upscale_factor)
    new_height = int(cropped_img.height * upscale_factor)
    
    # Upscale the cropped image
    upscaled_img = cropped_img.resize((new_width, new_height), Image.LANCZOS)

    # Increase the contrast
    enhancer = ImageEnhance.Contrast(upscaled_img)
    upscaled_img = enhancer.enhance(1.4)
    
    # Fetch text from the text URL
    timestamp = fetch_text_from_url(text_url)
    
    # Overlay text onto the image
    draw = ImageDraw.Draw(upscaled_img, 'RGBA')
    font = ImageFont.truetype("Avenir.ttc", 24)
    position = (1180,1590)
    left, top, right, bottom = draw.textbbox(position, timestamp, font=font, anchor='rd')
    draw.rectangle((left-5, top-5, right+5, bottom+1), fill=(20,20,20,150))
    draw.text(position, timestamp, font=font, fill="white", anchor='rd')
    # draw.text((1180,1590), timestamp, fill=(255, 255, 255), font=font, anchor='rd')
    
    # Save the final image
    upscaled_img.save(output_path)


# Specify the URL of the image, output image path, crop coordinates, and upscale factor
image_url = 'https://fog.today/current.jpg'
text_url = 'https://fog.today'
output_image_path = 'current-cropped-overlay.jpg'
crop_dim_x = 800 # x dimension of cropped area, in px. I.e, zoom level.
crop_corner = (320, 220) # upper left corner (x, y from upper left corner)

# this part calculates the input to the function
crop_dims = (crop_dim_x, crop_dim_x*4/3)
crop_coords = (crop_corner[0], 
               crop_corner[1], 
               crop_corner[0]+crop_dims[0], 
               crop_corner[1]+crop_dims[1])  # (left, upper, right, lower)
upscale_factor = 1200/crop_dim_x

# Print the current date and time
current_datetime = datetime.datetime.now()
formatted_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
print(formatted_datetime)

crop_and_upscale_image_with_overlay(image_url, text_url, output_image_path, *crop_coords, upscale_factor)

### push image to visionect

from vss_python_api import ApiDeclarations

load_dotenv()

my_api = ApiDeclarations(
    os.getenv("VISIONECT_API_URL"),
    os.getenv("VISIONECT_API_KEY"),
    os.getenv("VISIONECT_API_SECRET")
)
uuid = os.getenv("VISIONECT_DEVICE_UUID")

# push image
fr = {'image': ('img.jpg', open(output_image_path, 'rb'), 'image/jpg', {'Expires': '0'})}
sc = my_api.set_http(uuid, fr)
if sc != 200:
    print("Error pushing image! HTTP status code %s" % sc)
else:
    print("Successfully pushed image")