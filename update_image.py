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


def enhance_with_highlight_cap(
    base,
    contrast_factor,
    brightness_factor,
    max_near_white_fraction=0.2,
    white_threshold=250,
    search_iterations=24,
    brightness_floor=0.01,
):
    """
    Apply full contrast, then brightness, while respecting a highlight cap.

    contrast_factor: Always applied as given to ``ImageEnhance.Contrast``
    (``1.0`` unchanged; above ``1.0`` increases contrast; below flattens).

    brightness_factor: Target for ``ImageEnhance.Brightness`` after contrast
    (``1.0`` unchanged; above ``1.0`` brightens; below ``1.0`` darkens). If
    that setting would make more than ``max_near_white_fraction`` of pixels
    near-white (see ``white_threshold``), the brightness factor is reduced
    (never increased past your target) until the rule is met. Contrast is
    not changed by this adjustment.

    Order: contrast first, then brightness, same as ``ImageEnhance`` chaining.

    Returns:
        ``(image, brightness_applied)`` — the enhanced image and the
        ``ImageEnhance.Brightness`` factor actually used (after any capping).
    """
    contrasted = ImageEnhance.Contrast(base).enhance(contrast_factor)

    def near_white_frac_at(b):
        enhanced = ImageEnhance.Brightness(contrasted).enhance(b)
        return _fraction_near_white(enhanced, white_threshold)

    b_hi = max(brightness_floor, float(brightness_factor))
    if near_white_frac_at(b_hi) <= max_near_white_fraction:
        b_final = b_hi
        return ImageEnhance.Brightness(contrasted).enhance(b_final), b_final

    b_lo = brightness_floor
    if near_white_frac_at(b_lo) > max_near_white_fraction:
        b_final = b_lo
        return ImageEnhance.Brightness(contrasted).enhance(b_final), b_final

    lo, hi = b_lo, b_hi
    for _ in range(search_iterations):
        mid = (lo + hi) / 2.0
        if near_white_frac_at(mid) <= max_near_white_fraction:
            lo = mid
        else:
            hi = mid

    b_final = lo
    return ImageEnhance.Brightness(contrasted).enhance(b_final), b_final


def fetch_timestamp(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    timestamp = soup.find('div', {'id': 'timestamp'}).text.strip()
    return timestamp

def fetch_and_process_image(
    image_url,
    text_url,
    raw_image_path,
    final_image_path,
    crop_dim_x,
    crop_ul_corner,
    contrast_factor,
    brightness_factor,
    max_near_white_fraction,
    white_threshold,
):

    # Download the image from the image URL
    response = requests.get(image_url)
    img = Image.open(BytesIO(response.content))
    img.save(raw_image_path)

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
    upscaled_img, brightness_applied = enhance_with_highlight_cap(
        base,
        contrast_factor,
        brightness_factor,
        max_near_white_fraction=max_near_white_fraction,
        white_threshold=white_threshold,
    )
    print(
        "Final brightness factor: %.4f (target was %.4f)"
        % (brightness_applied, brightness_factor)
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
    upscaled_img.save(final_image_path)

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
raw_image_path = 'current-raw.jpg'
final_image_path = 'current-processed.jpg'
crop_dim_x = 800 # x dimension of cropped area, in px. I.e, zoom level.
crop_ul_corner = (320, 220) # upper left corner (x, y from upper left corner)
contrast_factor = 1.0
brightness_factor = 1.5
max_near_white_fraction = 0.05
white_threshold = 250

print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")) # Print the current date and time
fetch_and_process_image(image_url, text_url, raw_image_path, final_image_path, crop_dim_x, crop_ul_corner, contrast_factor, brightness_factor, max_near_white_fraction, white_threshold)
push_to_visionect(final_image_path)