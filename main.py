import pygame
import sys
import random

pygame.init()

WIDTH, HEIGHT = 900, 420
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("HRWM MVP - Dual Scenario Prototype v0.4.2")
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 28)

# ===== scenario =====
SCENARIO = "side_cross"   # "front_block" / "side_cross"

# ===== mode config =====
MODE_CONFIGS = [
    {"name": "full_scene", "low_freq_interval": None},
    {"name": "low_freq_10", "low_freq_interval": 10},
    {"name": "low_freq_5", "low_freq_interval": 5},
    {"name": "reflex_router", "low_freq_interval": None},
]

CURRENT_MODE_INDEX = 0
CURRENT_MODE = MODE_CONFIGS[CURRENT_MODE_INDEX]

# ===== episode config =====
EPISODES_PER_MODE = 10
episode = 1
results = []

# ===== randomness =====
BASE_SEED = 42

# ===== corridor =====
corridor_top = 100
corridor_bottom = 320
center_y = (corridor_top + corridor_bottom) // 2

# ===== agent =====
agent_start_x = 120
agent_radius = 15
agent_speed_x = 4

# ===== obstacle =====
obs_width = 42
obs_height = 80
obs_speed_x = -8
obs_speed_y = 8

stop_x_candidates = [300, 450, 600]
cross_x_candidates = [350, 450, 550]

# ===== event trigger =====
event_trigger_distance = 110

# ===== sensing / action =====
danger_x = 140
danger_y = 120
avoid_force = 5
recover_force = 2

# ===== colors =====
BG = (20, 20, 30)
ROAD = (90, 90, 90)
AGENT = (0, 200, 255)
OBSTACLE = (255, 80, 80)
DANGER_BOX = (255, 255, 0)
TEXT = (255, 255, 255)

# ===== runtime state =====
agent_x = agent_start_x
agent_y = center_y
agent_speed_y = 0.0

obs_x = 0.0
obs_y = 0.0
obs_vx = 0.0
obs_vy = 0.0

frame_count = 0
episode_steps = 0
scene_check_called = 0
collision_count = 0
reflex_trigger_count = 0
trigger_active_frames = 0

avoid_latched = False
avoid_dir = 0
prev_triggered = False
reflex_active = False

event_started = False
event_done = False
spawn_side = "top"

MAX_STEPS = 280

# ===== event stats =====
stop_x = 450


def setup_episode_event(episode_index: int) -> None:
    global stop_x, spawn_side

    seed_value = BASE_SEED + episode_index
    random.seed(seed_value)

    if SCENARIO == "front_block":
        stop_x = random.choice(stop_x_candidates)

    elif SCENARIO == "side_cross":
        stop_x = random.choice(cross_x_candidates)
        spawn_side = random.choice(["top", "bottom"])


def reset_episode() -> None:
    global agent_x, agent_y, agent_speed_y
    global obs_x, obs_y, obs_vx, obs_vy
    global frame_count, episode_steps
    global scene_check_called, collision_count, reflex_trigger_count, trigger_active_frames
    global avoid_latched, avoid_dir, prev_triggered, reflex_active
    global event_started, event_done

    agent_x = float(agent_start_x)
    agent_y = float(center_y)
    agent_speed_y = 0.0

    if SCENARIO == "front_block":
        obs_x = float(WIDTH + 40)
        obs_y = float(center_y - obs_height // 2)
        obs_vx = 0.0
        obs_vy = 0.0

    elif SCENARIO == "side_cross":
        obs_x = float(stop_x)

        if spawn_side == "top":
            obs_y = float(corridor_top - obs_height)
        else:
            obs_y = float(corridor_bottom)

        obs_vx = 0.0
        obs_vy = 0.0

    frame_count = 0
    episode_steps = 0
    scene_check_called = 0
    collision_count = 0
    reflex_trigger_count = 0
    trigger_active_frames = 0

    avoid_latched = False
    avoid_dir = 0
    prev_triggered = False
    reflex_active = False

    event_started = False
    event_done = False


def build_rects():
    danger_rect = pygame.Rect(
        int(agent_x),
        int(agent_y - danger_y // 2),
        danger_x,
        danger_y
    )

    obs_rect = pygame.Rect(
        int(obs_x),
        int(obs_y),
        obs_width,
        obs_height
    )

    agent_rect = pygame.Rect(
        int(agent_x - agent_radius),
        int(agent_y - agent_radius),
        agent_radius * 2,
        agent_radius * 2
    )

    return danger_rect, obs_rect, agent_rect


def scene_policy(obs_rect: pygame.Rect) -> bool:
    global scene_check_called

    scene_check_called += 1

    near_in_x = abs(obs_rect.centerx - agent_x) < 170
    near_in_y = abs(obs_rect.centery - agent_y) < 95

    return near_in_x and near_in_y


def compute_avoid_direction() -> int:
    if SCENARIO == "front_block":
        # If near center, bias upward first; otherwise continue away from center
        if agent_y <= center_y:
            return -1
        return 1

    if SCENARIO == "side_cross":
        # obstacle from top -> agent goes down
        # obstacle from bottom -> agent goes up
        if spawn_side == "top":
            return 1
        return -1

    return -1


def maybe_start_event() -> None:
    global event_started, obs_vx, obs_vy

    if event_started:
        return

    if abs(agent_x - stop_x) <= event_trigger_distance:
        event_started = True

        if SCENARIO == "front_block":
            obs_vx = float(obs_speed_x)

        elif SCENARIO == "side_cross":
            if spawn_side == "top":
                obs_vy = float(obs_speed_y)
            else:
                obs_vy = float(-obs_speed_y)


def maybe_update_obstacle() -> None:
    global obs_x, obs_y, obs_vx, obs_vy, event_done

    if SCENARIO == "front_block":
        obs_x += obs_vx

        if event_started and not event_done and obs_x <= stop_x:
            obs_x = float(stop_x)
            obs_vx = 0.0
            event_done = True

    elif SCENARIO == "side_cross":
        if event_started and not event_done:
            obs_y += obs_vy

            target_y = float(center_y - obs_height // 2)

            if spawn_side == "top":
                if obs_y >= target_y:
                    obs_y = target_y
                    obs_vy = 0.0
                    event_done = True
            else:
                if obs_y <= target_y:
                    obs_y = target_y
                    obs_vy = 0.0
                    event_done = True


def end_episode(success: bool) -> None:
    global episode, CURRENT_MODE_INDEX, CURRENT_MODE

    results.append({
        "mode": CURRENT_MODE["name"],
        "episode": episode,
        "success": 1 if success else 0,
        "collision": collision_count,
        "scene_checks": scene_check_called,
        "reflex_triggers": reflex_trigger_count,
        "steps": episode_steps,
        "scenario": SCENARIO,
        "stop_x": stop_x,
    })

    print(
        f'[{CURRENT_MODE["name"]}] '
        f'Episode {episode} | '
        f'success={success} | '
        f'collision={collision_count} | '
        f'scene_checks={scene_check_called} | '
        f'reflex_triggers={reflex_trigger_count} | '
        f'steps={episode_steps} | '
        f'scenario={SCENARIO} | stop_x={stop_x}'
    )

    episode += 1

    if episode > EPISODES_PER_MODE:
        episode = 1
        CURRENT_MODE_INDEX += 1

        if CURRENT_MODE_INDEX >= len(MODE_CONFIGS):
            print_summary()
            pygame.quit()
            sys.exit()

        CURRENT_MODE = MODE_CONFIGS[CURRENT_MODE_INDEX]

    setup_episode_event(episode)
    reset_episode()


def print_summary() -> None:
    print("\n========== SUMMARY ==========")

    for mode in MODE_CONFIGS:
        mode_name = mode["name"]
        mode_results = [r for r in results if r["mode"] == mode_name]
        total = len(mode_results)

        success_rate = sum(r["success"] for r in mode_results) / total
        collision_rate = sum(1 for r in mode_results if r["collision"] > 0) / total
        avg_scene_checks = sum(r["scene_checks"] for r in mode_results) / total
        avg_reflex_triggers = sum(r["reflex_triggers"] for r in mode_results) / total
        avg_steps = sum(r["steps"] for r in mode_results) / total

        print(f"\nMode: {mode_name}")
        print(f"Episodes: {total}")
        print(f"Success Rate: {success_rate:.2f}")
        print(f"Collision Rate: {collision_rate:.2f}")
        print(f"Avg Scene Checks: {avg_scene_checks:.2f}")
        print(f"Avg Reflex Triggers: {avg_reflex_triggers:.2f}")
        print(f"Avg Steps: {avg_steps:.2f}")


setup_episode_event(episode)
reset_episode()

running = True

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    frame_count += 1
    episode_steps += 1

    # move agent forward
    agent_x += agent_speed_x

    # event logic
    maybe_start_event()
    maybe_update_obstacle()

    danger_rect, obs_rect, agent_rect = build_rects()

    triggered = danger_rect.colliderect(obs_rect)
    safe_passed = (obs_rect.right < agent_x - agent_radius)

    should_avoid = False
    mode_name = CURRENT_MODE["name"]

    # ===== policy =====
    if mode_name == "full_scene":
        if scene_policy(obs_rect):
            avoid_latched = True
            avoid_dir = compute_avoid_direction()

        if safe_passed:
            avoid_latched = False
            avoid_dir = 0

        should_avoid = avoid_latched

    elif mode_name.startswith("low_freq"):
        interval = CURRENT_MODE["low_freq_interval"]

        if frame_count % interval == 0:
            if scene_policy(obs_rect):
                avoid_latched = True
                avoid_dir = compute_avoid_direction()

        if safe_passed:
            avoid_latched = False
            avoid_dir = 0

        should_avoid = avoid_latched

    elif mode_name == "reflex_router":
        # Enter reflex mode on first danger-box overlap
        if triggered and not prev_triggered:
            reflex_active = True

        prev_triggered = triggered

        # While reflex mode is active, keep doing high-frequency scene checks
        if reflex_active:
            reflex_trigger_count += 1

            if scene_policy(obs_rect):
                avoid_latched = True
                avoid_dir = compute_avoid_direction()

        if safe_passed:
            avoid_latched = False
            avoid_dir = 0
            reflex_active = False

        should_avoid = avoid_latched

    # ===== movement =====
    if should_avoid:
        agent_speed_y = avoid_force * avoid_dir

    elif not safe_passed:
        agent_speed_y = 0.0

    else:
        offset = center_y - agent_y
        agent_speed_y = max(
            -recover_force,
            min(recover_force, offset * 0.15)
        )

    agent_y += agent_speed_y

    # clamp
    min_y = corridor_top + agent_radius
    max_y = corridor_bottom - agent_radius

    if agent_y < min_y:
        agent_y = float(min_y)

    if agent_y > max_y:
        agent_y = float(max_y)

    # collision
    danger_rect, obs_rect, agent_rect = build_rects()
    collision = agent_rect.colliderect(obs_rect)

    if collision:
        collision_count += 1
        end_episode(False)

    elif episode_steps >= MAX_STEPS:
        end_episode(True)

    # ===== draw =====
    screen.fill(BG)

    pygame.draw.rect(
        screen,
        ROAD,
        (0, corridor_top, WIDTH, corridor_bottom - corridor_top)
    )

    pygame.draw.circle(
        screen,
        AGENT,
        (int(agent_x), int(agent_y)),
        agent_radius
    )

    pygame.draw.rect(screen, OBSTACLE, obs_rect)
    pygame.draw.rect(screen, DANGER_BOX, danger_rect, 2)

    mode_text = font.render(f"MODE: {CURRENT_MODE['name']}", True, TEXT)
    scenario_text = font.render(f"SCENARIO: {SCENARIO}", True, TEXT)
    ep_text = font.render(f"Episode: {episode}/{EPISODES_PER_MODE}", True, TEXT)
    check_text = font.render(f"scene checks: {scene_check_called}", True, TEXT)

    screen.blit(mode_text, (20, 20))
    screen.blit(scenario_text, (20, 50))
    screen.blit(ep_text, (20, 80))
    screen.blit(check_text, (20, 110))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()