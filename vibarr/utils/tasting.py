import math
from ..models import AppConfig

def calculate_tasting_count(runtime, season_episodes=0):
    """
    Calculates the number of episodes to taste for a TV show.
    Formula: max(min_floor, ceil(season_episodes * percentage)) + runtime_adjustment
    """
    config = AppConfig.get_solo()
    min_floor = config.default_tasting_count
    percentage = config.tasting_percentage / 100.0
    
    # Base count from percentage of first season
    if season_episodes > 0:
        base_count = math.ceil(season_episodes * percentage)
    else:
        base_count = min_floor
        
    # Ensure we don't go below the floor
    count = max(min_floor, base_count)
    
    # Runtime adjustment: shorter shows (comedies) need more episodes to judge
    # Typically < 30 mins means it's a sitcom/comedy
    if runtime and runtime < 35:
        count += 2
        
    return count
