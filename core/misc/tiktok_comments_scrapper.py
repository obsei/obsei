from pydantic import BaseModel

from typing import Optional, Any
import subprocess


class TiktokCommentsScrapper(BaseModel):
    ms_token: Optional[str] = None
    video_url: Optional[str] = None
    max_comments: Optional[int] = 20

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    async def fetch_tiktok_comments(self, until_datetime=None):
        try:
            command = "xvfb-run -a python3 libs/tiktok/process_tiktok.py " + self.video_url + " " + str(
                self.max_comments) + " " + str(self.ms_token) + " " + str(until_datetime.strftime("%Y-%m-%d %H:%M:%S"))
            subprocess.run(command, shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            print(f"Command failed with error: {e.output.decode('utf-8').strip()}")
            return False

        return True
