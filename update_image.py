import requests
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from bs4 import BeautifulSoup
from io import BytesIO
import datetime
import os
from dotenv import load_dotenv
from vss_python_api import ApiDeclarations


def _fraction_near_white(img, threshold=250):
    """Fraction of RGB pixels where R, G, B are all >= threshold (blown highlights)."""
    rgb = img.convert("RGB")
    buf = rgb.tobytes()
    mv = memoryview(buf)
    n = len(mv) // 3
    if n == 0:
        return 0.0
    w = 0
    for i in range(0, len(mv), 3):
        if mv[i] >= threshold and mv[i + 1] >= threshold and mv[i + 2] >= threshold:
            w += 1
    return w / n


def _apply_contrast_brightness(base, contrast_factor, brightness_factor):
    out = ImageEnhance.Contrast(base).enhance(contrast_factor)
    return ImageEnhance.Brightness(out).enhance(brightness_factor)


def enhance_with_highlight_cap(
    base,
    contrast_factor,
    brightness_factor,
    max_near_white_fraction=0.2,
    white_threshold=250,
    search_iterations=24,
):
    """
    Apply contrast then brightness like ImageEnhance, but scale both factors
    down from their targets (keeping 1.0 as neutral) so at most
    max_near_white_fraction of pixels are near-white after enhancement.

    contrast_factor: Passed to ``ImageEnhance.Contrast``. ``1.0`` leaves the
    image unchanged; values above ``1.0`` increase contrast (midtones spread
    toward black and white); below ``1.0`` flattens the image.

    brightness_factor: Passed to ``ImageEnhance.Brightness``. ``1.0`` is
    unchanged; above ``1.0`` brightens (can push highlights toward white);
    below ``1.0`` darkens.

    Enhancement order matches the rest of this script: contrast first, then
    brightness. When capping is active, both factors are scaled together as
    ``1 + (factor - 1) * scale`` with ``scale`` in ``[0, 1]``.
    """
    def scaled_factors(scale):
        c = 1.0 + (contrast_factor - 1.0) * scale
        b = 1.0 + (brightness_factor - 1.0) * scale
        return c, b

    def near_white_frac_at(scale):
        c, b = scaled_factors(scale)
        enhanced = _apply_contrast_brightness(base, c, b)
        return _fraction_near_white(enhanced, white_threshold)

    if near_white_frac_at(1.0) <= max_near_white_fraction:
        c, b = scaled_factors(1.0)
        return _apply_contrast_brightness(base, c, b)

    lo, hi = 0.0, 1.0
    for _ in range(search_iterations):
        mid = (lo + hi) / 2.0
        if near_white_frac_at(mid) <= max_near_white_fraction:
            lo = mid
        else:
            hi = mid

    c, b = scaled_factors(lo)
    return _apply_contrast_brightness(base, c, b)


def fetch_timestamp(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    timestamp = soup.find('div', {'id': 'timestamp'}).text.strip()
    return timestamp

def fetch_and_process_image(
    image_url,
    text_url,
    output_path,
    crop_dim_x,
    crop_ul_corner,
    contrast_factor=1.4,
    brightness_factor=1.5,
    max_near_white_fraction=0.1,
    white_threshold=250,
):

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

    # Increase contrast and brightness, capped so highlights do not blow out
    base = upscaled_img.copy()
    upscaled_img = enhance_with_highlight_cap(
        base,
        contrast_factor,
        brightness_factor,
        max_near_white_fraction=max_near_white_fraction,
        white_threshold=white_threshold,
    )
    
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