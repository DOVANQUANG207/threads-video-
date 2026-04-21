from PIL import Image
import numpy as np

def check_text(f):
    try:
        img = np.array(Image.open(f).convert('RGB'))
        mask = (img[:,:,0]>200) & (img[:,:,1]>200) & (img[:,:,2]>200)
        x = np.where(mask)[1]
        return x.min() if len(x) > 0 else 'N/A'
    except Exception as e:
        return str(e)

print('core text:', check_text('test_core.png'))
print('p1 text:', check_text('test_p1.png'))
print('p2 text:', check_text('test_p2.png'))
print('p3 text:', check_text('test_p3.png'))
print('x1 text:', check_text('test_x1.png'))
