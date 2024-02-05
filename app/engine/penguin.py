
from __future__ import annotations

from typing import TYPE_CHECKING, Any, List

if TYPE_CHECKING:
    from app.objects.ninjas import Ninja
    from app.engine.game import Game

from twisted.internet.address import IPv4Address, IPv6Address
from twisted.internet.protocol import Factory
from twisted.python.failure import Failure

from app.protocols import MetaplaceProtocol
from app.data import (
    Penguin as PenguinObject,
    BuildType,
    EventType,
    Phase,
    Card
)

import app.session

class Penguin(MetaplaceProtocol):
    def __init__(self, server: Factory, address: IPv4Address | IPv6Address):
        super().__init__(server, address)

        self.battle_mode: int = 0
        self.screen_size: str = ''
        self.asset_url: str = ''

        self.object: PenguinObject | None = None
        self.ninja: "Ninja" | None = None
        self.game: "Game" | None = None
        self.element: str = ""

        self.tip_mode: bool = True
        self.last_tip: Phase | None = None
        self.displayed_tips: List[Phase] = []
        self.power_cards: List[Card] = []

        self.in_queue: bool = False
        self.is_ready: bool = False
        self.was_ko: bool = False

    def __repr__(self) -> str:
        return f"<{self.name} ({self.pid})>"

    @property
    def is_member(self) -> bool:
        return True # TODO

    @property
    def in_game(self) -> bool:
        return self.game is not None

    @property
    def power_cards_water(self) -> List[Card]:
        return [c for c in self.power_cards if c.element == 'w']

    @property
    def power_cards_fire(self) -> List[Card]:
        return [c for c in self.power_cards if c.element == 'f']

    @property
    def power_cards_snow(self) -> List[Card]:
        return [c for c in self.power_cards if c.element == 's']

    def command_received(self, command: str, args: List[Any]):
        try:
            app.session.events.call(
                self,
                command,
                args
            )
        except Exception as e:
            self.logger.error(f'Failed to execute event: {e}', exc_info=e)
            self.close_connection()
            return

    def close_connection(self):
        if self.logged_in:
            self.send_to_room()

        # Put client in ready state, so that the game doesn't softlock
        self.is_ready = True

        return super().close_connection()

    def connectionLost(self, reason: Failure | None = None) -> None:
        if self.in_game and self.ninja:
            self.ninja.set_health(0)

        if reason is not None and not self.disconnected:
            self.logger.warning(f"Connection lost: {reason.getErrorMessage()}")

        self.server.matchmaking.remove(self)
        self.server.players.remove(self)
        self.disconnected = True

    def send_to_room(self) -> None:
        # This will load a window, that sends the player back to the room
        window = self.window_manager.get_window('cardjitsu_snowexternalinterfaceconnector.swf')
        window.layer = 'toolLayer'
        window.load(type=EventType.IMMEDIATE.value)

    def send_error(self, message: str) -> None:
        window = self.window_manager.get_window('cardjitsu_snowerrorhandler.swf')
        window.send_payload(
            'error',
            {
                'msg': message,
                'code': 0, # TODO
                'data': '' # TODO
            }
        )

    def send_tip(self, phase: Phase) -> None:
        infotip = self.window_manager.get_window('cardjitsu_snowinfotip.swf')
        infotip.layer = 'topLayer'
        infotip.load(
            {
                'element': self.element,
                'phase': phase.value,
            },
            loadDescription="",
            assetPath="",
            xPercent=0.1,
            yPercent=0
        )
        self.last_tip = phase

        def on_close(client: "Penguin"):
            client.last_tip = None

        infotip.on_close = on_close

    def hide_tip(self) -> None:
        infotip = self.window_manager.get_window('cardjitsu_snowinfotip.swf')
        infotip.send_payload('disable')

    def initialize_game(self) -> None:
        self.send_tag('P_MAPBLOCK', 't', 1, 1, 'iVBORw0KGgoAAAANSUhEUgAAAAkAAAAFCAAAAACyOJm3AAAADklEQVQImWNghgEGIlkADWEAiDEh28IAAAAASUVORK5CYII=')
        self.send_tag('P_MAPBLOCK', 'h', 1, 1, 'iVBORw0KGgoAAAANSUhEUgAAAAoAAAAGCAAAAADfm1AaAAAADklEQVQImWOohwMG8pgA1rMdxRJRFewAAAAASUVORK5CYII=')

        self.send_tag('UI_ALIGN', self.server.world_id, 0, 0, 'center', 'scale_none')
        self.send_tag('UI_BGCOLOR', 34, 164, 243)
        self.send_tag('W_PLACE', 0, 1, 0)

        self.send_tag('P_ZOOMLIMIT', -1.000000, -1.000000)
        self.send_tag('P_RENDERFLAGS', 0, 48)
        self.send_tag('P_SIZE', 9, 5)
        self.send_tag('P_VIEW', 5)
        self.send_tag('P_START', 5, 2.5, 0)
        self.send_tag('P_LOCKVIEW', 0)
        self.send_tag('P_TITLESIZE', 100)
        self.send_tag('P_ELEVSCALE', 0.031250)
        self.send_tag('P_RELIEF', 1)
        self.send_tag('P_LOCKSCROLL', 1, 0, 0, 0)
        self.send_tag('P_LOCKOBJECTS', 0)
        self.send_tag('P_HEIGHTMAPSCALE', 0.5, 0)
        self.send_tag('P_HEIGHTMAPDIVISION', 1)
        self.send_tag('P_CAMERA3D', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 864397819904.000000, 0, 0, 0, 0, 0, 0, 0)
        self.send_tag('P_DRAG', 0)
        self.send_tag('P_CAMLIMITS', 0, 0, 0, 0)
        self.send_tag('P_LOCKRENDERSIZE', 0, 1024, 768)
        self.send_tag('P_ASSETSCOMPLETE')

        # TODO: Find out what all of the tags do

    def send_login_reply(self):
        self.send_tag(
            'S_LOGIN',
            self.pid
        )

    def send_login_message(self, message: str):
        self.send_tag(
            'S_LOGINDEBUG',
            message
        )

    def send_login_error(self, code: int = 900):
        self.send_tag(
            'S_LOGINDEBUG',
            f'user code {code}'
        )

    def send_world_type(self):
        self.send_tag(
            'S_WORLDTYPE',
            self.server.server_type.value,
            self.server.build_type.value
        )

    def send_world(self):
        self.send_tag(
            'S_WORLD',
            self.server.world_id,                                  # World ID
            self.server.world_name,                                # World Name
            '0:113140001',                                         # start_placeUniqueId ???
            1 if self.server.build_type == BuildType.DEBUG else 0, # devMode
            'none',                                                # ?
            0,                                                     # ?
            'crowdcontrol',                                        # ?
            self.server.world_name,                                # clean_name
            0,                                                     # ?
            self.server.stylesheet_id,                             # STYLESHEET_ID ?
            0                                                      # ?
        )
