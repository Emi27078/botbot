from helper.game import Game
from lib.interact.tile import Tile
from lib.interface.events.moves.move_place_tile import MovePlaceTile
from lib.interface.events.moves.move_place_meeple import (
    MovePlaceMeeple,
    MovePlaceMeeplePass,
)
from lib.interface.queries.typing import QueryType
from lib.interface.queries.query_place_tile import QueryPlaceTile
from lib.interface.queries.query_place_meeple import QueryPlaceMeeple
from lib.interface.events.moves.typing import MoveType
from lib.config.map_config import MAX_MAP_LENGTH
from lib.config.map_config import MONASTARY_IDENTIFIER
from lib.interact.structure import StructureType
from lib.interact.tile import TileModifier


'''
python3 match_simulator.py --submissions 1:example_submissions/chet2.py 3:example_submissions/complex.py --engine

Tile: tileID and placed position

'''
class BotState:
    """A class for us to locally the state of the game and what we find relevant"""

    def __init__(self):
        self.last_tile: Tile | None = None
        self.meeples_placed: int = 0

def main():
    game = Game()
    bot_state = BotState()
    while True:
        # game says its ur turn, it could either be prompting u to put a tile
        # or a meeple
        query = game.get_next_query()
        

        def choose_move(query: QueryType)-> MoveType:
            match query:
                #if the game is asking do u want to put a tile
                case QueryPlaceTile() as q:
                    #tile putting logic
                    return handle_place_tile(game, bot_state, q)
                # if game is asking do u want to put a meeple on the tile
                case QueryPlaceMeeple() as q:
                    #meeple putting logic
                    print("meeple?")
                    return handle_place_meeple(game, bot_state, q)

        game.send_move(choose_move(query))

        

def handle_place_tile(game: Game, bot_state: BotState, query: QueryPlaceTile) -> MovePlaceTile:
    grid = game.state.map._grid
    placed_tiles = game.state.map.placed_tiles

    directions = {
        (1, 0): "left_edge",
        (0, 1): "top_edge",
        (-1, 0): "right_edge",
        (0, -1): "bottom_edge",
    }
    

    # see if the tile is river 
    river_move = try_place_river_tile(game, bot_state, query)
    if river_move:
        return river_move

    best_score = float("-inf")
    best_move = None

    my_meeples = game.state.get_meeples_placed_by(game.state.me.player_id)
    for meeple in my_meeples:
        for y in range(MAX_MAP_LENGTH):
            for x in range(MAX_MAP_LENGTH):
                tile = grid[y][x]
                if tile is None:
                    continue
                for edge, claimed_meeple in tile.internal_claims.items():
                    if claimed_meeple != meeple:
                        continue

                    for (dx, dy), opp_edge in directions.items():
                        nx, ny = x + dx, y + dy
                        if not (0 <= nx < MAX_MAP_LENGTH and 0 <= ny < MAX_MAP_LENGTH):
                            continue
                        if grid[ny][nx] is not None:
                            continue

                        for tile_hand_index, original_tile in enumerate(game.state.my_tiles):
                            for rotation in range(4):
                                test_tile = Tile(
                                    tile_id=original_tile.tile_type,
                                    left_edge=original_tile.internal_edges.left_edge,
                                    right_edge=original_tile.internal_edges.right_edge,
                                    top_edge=original_tile.internal_edges.top_edge,
                                    bottom_edge=original_tile.internal_edges.bottom_edge,
                                    modifiers=original_tile.modifiers.copy(),
                                )
                                test_tile.rotate_clockwise(rotation)

                                if game.can_place_tile_at(test_tile, nx, ny):
                                    my_edge = directions[(-dx, -dy)]
                                    if StructureType.is_compatible(
                                        test_tile.internal_edges[my_edge],
                                        tile.internal_edges[opp_edge],
                                    ):
                                        score = score_tile_placement(game, test_tile, nx, ny, greedy_bonus=5)
                                        if score > best_score:
                                            best_score = score
                                            best_move = (tile_hand_index, test_tile, nx, ny)

    if best_move is None:
        for placed_tile in placed_tiles:
            x0, y0 = placed_tile.placed_pos
            for (dx, dy), _ in directions.items():
                nx, ny = x0 + dx, y0 + dy
                if not (0 <= nx < MAX_MAP_LENGTH and 0 <= ny < MAX_MAP_LENGTH):
                    continue
                if grid[ny][nx] is not None:
                    continue

                for tile_hand_index, original_tile in enumerate(game.state.my_tiles):
                    for rotation in range(4):
                        test_tile = Tile(
                            tile_id=original_tile.tile_type,
                            left_edge=original_tile.internal_edges.left_edge,
                            right_edge=original_tile.internal_edges.right_edge,
                            top_edge=original_tile.internal_edges.top_edge,
                            bottom_edge=original_tile.internal_edges.bottom_edge,
                            modifiers=original_tile.modifiers.copy(),
                        )
                        test_tile.rotate_clockwise(rotation)
                        if game.can_place_tile_at(test_tile, nx, ny):
                            score = score_tile_placement(game, test_tile, nx, ny)
                            if score > best_score:
                                best_score = score
                                best_move = (tile_hand_index, test_tile, nx, ny)

    if best_move:
        tile_hand_index, best_tile, x, y = best_move
        best_tile.placed_pos = (x, y)
        bot_state.last_tile = best_tile
        actual_tile = game.state.my_tiles[tile_hand_index]
        while actual_tile.rotation != best_tile.rotation:
            actual_tile.rotate_clockwise(1)
        return game.move_place_tile(query, best_tile._to_model(), tile_hand_index)
    
def try_place_river_tile(game: Game, bot_state: BotState, query: QueryPlaceTile) -> MovePlaceTile | None:
    grid = game.state.map._grid
    directions = {
        (1, 0): "left_edge",
        (0, 1): "top_edge",
        (-1, 0): "right_edge",
        (0, -1): "bottom_edge",
    }

    placed_tiles = game.state.map.placed_tiles

    for placed_tile in placed_tiles:
        placed_pos = placed_tile.placed_pos

        for tile_hand_index, tile_in_hand in enumerate(game.state.my_tiles):
            has_river = any(tile_in_hand.internal_edges[edge] == StructureType.RIVER for edge in directions.values())
            if not has_river:
                continue


            for (dx, dy), edge in directions.items():
                target_x = placed_pos[0] + dx
                target_y = placed_pos[1] + dy

                if not (0 <= target_x < MAX_MAP_LENGTH and 0 <= target_y < MAX_MAP_LENGTH):
                    continue
                if grid[target_y][target_x] is not None:
                    continue

                if game.can_place_tile_at(tile_in_hand, target_x, target_y):
                        print(f"Checking edge: {tile_in_hand.internal_edges[edge]}")

                        if tile_in_hand.internal_edges[edge] == StructureType.RIVER:
                            uturn_check = False
                            for tile_edge in directions.values():
                                if (
                                    tile_edge == edge
                                    or tile_in_hand.internal_edges[tile_edge]
                                    != StructureType.RIVER
                                ):
                                    continue

                                forcast_coordinates_one = {
                                    "top_edge": (0, -1),
                                    "right_edge": (1, 0),
                                    "bottom_edge": (0, 1),
                                    "left_edge": (-1, 0),
                                }
                                
                                extension = forcast_coordinates_one[tile_edge]
                                forecast_x = target_x + extension[0]
                                forecast_y = target_y + extension[1]
                                print(forecast_x, forecast_y)
                                
                                # Check direct adjacency for U-turn
                                for coords in forcast_coordinates_one.values():
                                    checking_x = forecast_x + coords[0]
                                    checking_y = forecast_y + coords[1]
                                    if checking_x != target_x or checking_y != target_y:
                                        if grid[checking_y][checking_x] is not None:
                                            print("Direct U-turn detected")
                                            uturn_check = True
                                            
                                # Second level of forecast: extended prediction
                                forcast_coordinates_two = {
                                    "top_edge": (0, -2),
                                    "right_edge": (2, 0),
                                    "bottom_edge": (0, 2),
                                    "left_edge": (-2, 0),
                                }
                                extension = forcast_coordinates_two[tile_edge]
                                forecast_x = target_x + extension[0]
                                forecast_y = target_y + extension[1]
                                
                                # Check extended adjacency for U-turn
                                for coords in forcast_coordinates_one.values():
                                    checking_x = forecast_x + coords[0]
                                    checking_y = forecast_y + coords[1]
                                    if grid[checking_y][checking_x] is not None:
                                        uturn_check = True

                            if uturn_check:
                                tile_in_hand.rotate_clockwise(1)
                                if tile_in_hand.internal_edges[edge] != StructureType.RIVER:
                                    tile_in_hand.rotate_clockwise(2)

                            
                            if not game.can_place_tile_at(tile_in_hand, target_x, target_y):
                                    continue
                            print(f"Placing tile at {target_x}, {target_y}")
                            bot_state.last_tile = tile_in_hand
                            bot_state.last_tile.placed_pos = (target_x, target_y)

                            # Return the move
                            return game.move_place_tile(query, tile_in_hand._to_model(), tile_hand_index)
    return None


def score_tile_placement(game: Game, tile: Tile, x: int, y: int, greedy_bonus: int = 0) -> int:
    score = greedy_bonus
    grid = game.state.map._grid
    my_id = game.state.me.player_id

    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if not (0 <= nx < MAX_MAP_LENGTH and 0 <= ny < MAX_MAP_LENGTH):
                continue
            neighbor = grid[ny][nx]
            if neighbor and TileModifier.MONASTARY in neighbor.modifiers:
                monastery_owner = neighbor.internal_claims.get("MONASTARY")
                if monastery_owner and monastery_owner.player_id == my_id:
                    score += 3
                else:
                    score += 1

    directions = {
        (0, -1): "top_edge",
        (1, 0): "right_edge",
        (0, 1): "bottom_edge",
        (-1, 0): "left_edge",
    }
    opposite = {
        "top_edge": "bottom_edge",
        "bottom_edge": "top_edge",
        "left_edge": "right_edge",
        "right_edge": "left_edge",
    }

    for (dx, dy), edge in directions.items():
        nx, ny = x + dx, y + dy
        if not (0 <= nx < MAX_MAP_LENGTH and 0 <= ny < MAX_MAP_LENGTH):
            continue
        neighbor = grid[ny][nx]
        if neighbor:
            neighbor_edge = opposite[edge]
            claim = neighbor.internal_claims.get(neighbor_edge)
            if claim:
                if claim.player_id == my_id:
                    score += 4
    completed_now = game.state.check_any_complete(tile)
    if completed_now:
        score += 4 * len(completed_now)

    if TileModifier.EMBLEM in tile.modifiers:
        score += 2
    return score



def handle_place_meeple(game: Game, bot_state: BotState, query: QueryPlaceMeeple) -> MovePlaceMeeplePass | MovePlaceMeeple:
    tile = bot_state.last_tile
    my_id = game.state.me.player_id
    meeples_in_use = len(game.state.get_meeples_placed_by(my_id))

    if not tile or meeples_in_use >= 7:
        return game.move_place_meeple_pass(query)
    
    tiles_left = len(game.state.map.available_tiles)

# How many opponents are in the game?
    num_other_players = max(1, len(game.state.players) - 1) 

    # running out of meeples
    if meeples_in_use >= tiles_left // num_other_players + 1:
        return game.move_place_meeple_pass(query)

    completed_edges = set(game.state.check_any_complete(tile))

    structures = game.state.get_placeable_structures(tile._to_model())

    priority_order = [StructureType.MONASTARY, StructureType.CITY, StructureType.ROAD]

    for priority in priority_order:
        for edge, structure in structures.items():
            if structure != priority:
                continue

            if edge in completed_edges:
                continue

            if tile.internal_claims.get(edge):
                continue 

            claims = game.state._get_claims(tile, edge)
            if not claims:
                bot_state.meeples_placed += 1
                return game.move_place_meeple(query, tile._to_model(), edge)

    return game.move_place_meeple_pass(query)


if __name__ == "__main__":
    main()