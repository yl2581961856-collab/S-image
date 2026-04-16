import torch
import torch.nn functional as F

def catvtion_forward(Ip, Ig, vae, unet, scheduler, M=None, mask_free=True):
    """
    
    Ip: [B, 3, H, W] target person image
    Ig: [B, 3, H, W] garment image
    M : [B, 1, H, W] binary mask of the garment region (optional)
    """
    
# (1) 输入人像 Ii
if mask_free:
    Ii = Ip
else:
    Ii = Ip * M  # Hadmard逐元素乘
    
# （2） 空间维拼接后编码到Lantent空间
x_in = torch.cat([Ii, Ig], dim=1)  # [B, 6, H, W]
Xi = vae.encode(x_in).latent_dist.sample() * vae.config.scaling_factor #B, C, H', W']
 # Xi ~ [B, 4, H/8, W/8]
 
 # （3） mask-based迭代去噪  Mi
 if not mask_free:
     M_cat = torch.cat([M, torch.zeros_like(M)], dim=1)  # [B, 2, H, W]
     Mi = F.interpolate(M_cat, size=Xi.shape[2:], mode='nearest')  # [B, 2, H/8, W/8]
     
# 初始噪声
z = torch.randn_like(Xi)  # [B, C, H/8, W/8]    


# (4) 去噪迭代

for t in scheduler.timesteps:
    if mask_free:
        cond = torch.cat([z, Xi], dim=1)
    else:
        cond = torch.cat([z, Xi, Mi], dim=1)
        
    eps = unet(cond, t).sample
    z = scheduler.step(eps, t, z).prev_sample
    
    z0 = z
    
# (5) 按宽度切分，取person部分再解码
    z_person, _ = torch.chunk(z0, 2, dim=-1)  # each width half
    out = vae.decode(z_person / vae.config.scaling_factor).sample  # [B,3,H,W]
    return out