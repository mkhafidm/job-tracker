import random
import os
from typing import List, Optional, Any, Callable

def load_proxies(proxy_file: str = "proxies/valid_proxies.txt") -> List[str]:
    try:
        with open(proxy_file, "r") as f:
            proxies = [line.strip() for line in f if line.strip()]
        print(f"Loaded {len(proxies)} proxies from {proxy_file}")
        return proxies
    except FileNotFoundError:
        print(f"roxy file {proxy_file} not found. Running without proxy.")
        return []
    except Exception as e:
        print(f"Error loading proxy file: {e}")
        return []

def get_random_proxy(proxies: List[str]) -> Optional[str]:
    if proxies:
        return random.choice(proxies)
    return None

class ProxyRotator:
    def __init__(self, proxies: List[str]):
        self.proxies = proxies
        self.index = 0

    def next(self) -> Optional[str]:
        if not self.proxies:
            return None
        proxy = self.proxies[self.index % len(self.proxies)]
        self.index += 1
        return proxy


def execute_with_retry(
    scrape_func: Callable[..., Any],  
    rotator: ProxyRotator,          
    max_retries: int = 5,         
    *args,                           
    **kwargs                        
) -> Optional[Any]:
    for attempt in range(max_retries):
        proxy = rotator.next()
        if not proxy:
            print(f"No more proxies available for {scrape_func.__name__}.")
            return None
        
        proxy_config = {"http": f"http://{proxy}", "https": f"http://{proxy}"}
        print(f"Attempt {attempt+1}/{max_retries} for {scrape_func.__name__} using proxy {proxy}...")
        
        try:
            result = scrape_func(*args, **kwargs, proxies=proxy_config)
            if result:
                print(f"{scrape_func.__name__} succes using proxy {proxy}.")
                return result
            else:
                print(f"{scrape_func.__name__} returned empty result with proxy {proxy}. Trying next...")
        except Exception as e:
            print(f"{scrape_func.__name__} error with proxy {proxy}: {e}. Trying next...")
    
    print(f"All {max_retries} attempts for {scrape_func.__name__} failed.")
    return None
