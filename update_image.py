import requests
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from bs4 import BeautifulSoup
from io import BytesIO
import datetime
import os
from dotenv import load_dotenv
from vss_python_api import ApiDeclarations

def fetch_timestamp(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    timestamp = soup.find('div', {'id': 'timestamp'}).text.strip()
    return timestamp

def fetch_and_process_image(image_url, text_url, output_path,
                            crop_dim_x, crop_ul_corner, contrast_factor=1.4):

    # Download the image from the image URL
    response = requests.get(image_url)
    img = Image.open(BytesIO(response.content))
    
    # Crop the image
    crop_dims = (crop_dim_x, crop_dim_x*4/3) # x and y dimensions of the crop
    crop_coords = (crop_ul_corner[0], 
                crop_ul_corner[1], 
                crop_ul_corner[0]+crop_dims[0], 
                crop_ul_corner[1]+crop_dims[1])  # (left, upper, right, lower)
    cropped_img = img.crop((crop_coords[0], 
                            crop_coords[1], 
                            crop_coords[2], 
                            crop_coords[3])) # (left, upper, right, lower)
    
    # Calculate the new dimensions for upscale
    upscale_factor = 1200/crop_dim_x
    new_width = int(cropped_img.width * upscale_factor)
    new_height = int(cropped_img.height * upscale_factor)
    
    # Upscale the cropped image
    upscaled_img = cropped_img.resize((new_width, new_height), Image.LANCZOS)

    # Increase the contrast
    enhancer = ImageEnhance.Contrast(upscaled_img)
    upscaled_img = enhancer.enhance(contrast_factor)
    
    # Fetch text from the text URL
    timestamp = fetch_timestamp(text_url)
    
    # Overlay text onto the image
    draw = ImageDraw.Draw(upscaled_img, 'RGBA')
    font = ImageFont.truetype("Avenir.ttc", 24)
    position = (1180,1590)
    left, top, right, bottom = draw.textbbox(position, timestamp, font=font, anchor='rd')
    draw.rectangle((left-5, top-5, right+5, bottom+1), fill=(20,20,20,150))
    draw.text(position, timestamp, font=font, fill="white", anchor='rd')
    
    # Save the final image
    upscaled_img.save(output_path)

def push_to_visionect(img_path='current-processed.jpg'):
    load_dotenv()
    my_api = ApiDeclarations(
        os.getenv("VISIONECT_API_URL"),
        os.getenv("VISIONECT_API_KEY"),
        os.getenv("VISIONECT_API_SECRET")
    )
    uuid = os.getenv("VISIONECT_DEVICE_UUID")

    fr = {'image': ('img.jpg', open(img_path, 'rb'), 'image/jpg', {'Expires': '0'})}
    sc = my_api.set_http(uuid, fr)
    if sc != 200:
        print("Error pushing image! HTTP status code %s" % sc)
    else:
        print("Successfully pushed image")

# Specify the URL of the image, output image path, crop coordinates, and upscale factor
image_url = 'https://fog.today/current.jpg'
text_url = 'https://fog.today'
image_path = 'current-processed.jpg'
crop_dim_x = 800 # x dimension of cropped area, in px. I.e, zoom level.
crop_ul_corner = (320, 220) # upper left corner (x, y from upper left corner)

print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")) # Print the current date and time
fetch_and_process_image(image_url, text_url, image_path, crop_dim_x, crop_ul_corner)
push_to_visionect(image_path)