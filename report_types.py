"""
Registry of every channel-scoped YouTube Reporting API report.

Source: https://developers.google.com/youtube/reporting/v1/reports/channel_reports

We schedule a job for each so data starts accruing immediately. Reports expire
(60 days for regular, 30 for historical backfill), so the collector's whole
purpose is to pull each daily CSV once and archive it permanently as a JSON
shard. Anything not collected before expiry is gone for good.

The dimensions/metrics lists are documentation, not validation -- the collector
always reads the actual CSV header row, because Google explicitly warns that
column order is not guaranteed and new metrics may be appended over time.

`priority` controls scheduling and collection order only. If one report type is
unavailable for this channel, the collector logs it and continues; a single bad
report must never block the rest.
"""

CHANNEL_REPORTS = {
    # --- Reach: the reason this project exists.
    # Thumbnail impressions and CTR exist ONLY here. The Analytics API has no
    # equivalent metric at all.
    "channel_reach_basic_a1": {
        "priority": 1,
        "label": "Reach basic (impressions + CTR)",
        "dimensions": ["date", "channel_id", "video_id"],
        "metrics": ["video_thumbnail_impressions", "video_thumbnail_impressions_ctr"],
    },
    "channel_reach_combined_a1": {
        "priority": 2,
        "label": "Reach by traffic source, OS and device",
        "dimensions": ["date", "channel_id", "video_id", "traffic_source_type",
                       "traffic_source_detail", "operating_system", "device_type"],
        "metrics": ["video_thumbnail_impressions", "video_thumbnail_impressions_ctr"],
    },

    # --- Core video activity
    "channel_basic_a3": {
        "priority": 3,
        "label": "User activity (views, watch time, engagement)",
        "dimensions": ["date", "channel_id", "video_id", "live_or_on_demand",
                       "subscribed_status", "country_code"],
        "metrics": ["views", "engaged_views", "comments", "likes", "dislikes",
                    "videos_added_to_playlists", "videos_removed_from_playlists",
                    "shares", "watch_time_minutes", "average_view_duration_seconds",
                    "average_view_duration_percentage", "subscribers_gained",
                    "subscribers_lost", "red_views", "red_watch_time_minutes"],
    },
    "channel_traffic_source_a3": {
        "priority": 4,
        "label": "Traffic sources",
        "dimensions": ["date", "channel_id", "video_id", "live_or_on_demand",
                       "subscribed_status", "country_code",
                       "traffic_source_type", "traffic_source_detail"],
        "metrics": ["views", "engaged_views", "watch_time_minutes",
                    "average_view_duration_seconds",
                    "average_view_duration_percentage"],
    },
    "channel_combined_a3": {
        "priority": 5,
        "label": "Combined (playback location + traffic + device)",
        "dimensions": ["date", "channel_id", "video_id", "live_or_on_demand",
                       "subscribed_status", "country_code", "playback_location_type",
                       "traffic_source_type", "device_type", "operating_system"],
        "metrics": ["views", "engaged_views", "watch_time_minutes",
                    "average_view_duration_seconds",
                    "average_view_duration_percentage"],
    },
    "channel_device_os_a3": {
        "priority": 6,
        "label": "Device type and operating system",
        "dimensions": ["date", "channel_id", "video_id", "live_or_on_demand",
                       "subscribed_status", "country_code",
                       "device_type", "operating_system"],
        "metrics": ["views", "engaged_views", "watch_time_minutes",
                    "average_view_duration_seconds",
                    "average_view_duration_percentage"],
    },
    "channel_playback_location_a3": {
        "priority": 7,
        "label": "Playback locations",
        "dimensions": ["date", "channel_id", "video_id", "live_or_on_demand",
                       "subscribed_status", "country_code",
                       "playback_location_type", "playback_location_detail"],
        "metrics": ["views", "engaged_views", "watch_time_minutes",
                    "average_view_duration_seconds",
                    "average_view_duration_percentage"],
    },
    "channel_province_a3": {
        "priority": 8,
        "label": "User activity by US province",
        "dimensions": ["date", "channel_id", "video_id", "live_or_on_demand",
                       "subscribed_status", "country_code", "province_code"],
        "metrics": ["views", "engaged_views", "watch_time_minutes",
                    "average_view_duration_seconds",
                    "average_view_duration_percentage"],
    },
    "channel_subtitles_a3": {
        "priority": 9,
        "label": "Subtitles / caption language",
        "dimensions": ["date", "channel_id", "video_id", "live_or_on_demand",
                       "subscribed_status", "country_code",
                       "subtitle_language", "subtitle_language_autotranslated"],
        "metrics": ["views", "engaged_views", "watch_time_minutes",
                    "average_view_duration_seconds",
                    "average_view_duration_percentage"],
    },

    # --- Audience
    "channel_demographics_a1": {
        "priority": 10,
        "label": "Viewer demographics (age + gender)",
        "dimensions": ["date", "channel_id", "video_id", "live_or_on_demand",
                       "subscribed_status", "country_code", "age_group", "gender"],
        "metrics": ["views_percentage"],
    },
    "channel_sharing_service_a2": {
        "priority": 11,
        "label": "Content sharing by platform",
        "dimensions": ["date", "channel_id", "video_id", "live_or_on_demand",
                       "subscribed_status", "country_code", "sharing_service"],
        "metrics": ["shares"],
    },

    # --- In-video elements
    "channel_cards_a1": {
        "priority": 12,
        "label": "Cards",
        "dimensions": ["date", "channel_id", "video_id", "live_or_on_demand",
                       "subscribed_status", "country_code", "card_type", "card_id"],
        "metrics": ["card_impressions", "card_clicks", "card_click_rate",
                    "card_teaser_impressions", "card_teaser_clicks",
                    "card_teaser_click_rate"],
    },
    "channel_end_screens_a2": {
        "priority": 13,
        "label": "End screens",
        "dimensions": ["date", "channel_id", "video_id", "live_or_on_demand",
                       "subscribed_status", "country_code",
                       "end_screen_element_type", "end_screen_element_id"],
        "metrics": ["end_screen_element_impressions", "end_screen_element_clicks",
                    "end_screen_element_click_rate"],
    },
    "channel_annotations_a2": {
        "priority": 14,
        "label": "Annotations (legacy)",
        "dimensions": ["date", "channel_id", "video_id", "live_or_on_demand",
                       "subscribed_status", "country_code",
                       "annotation_type", "annotation_id"],
        "metrics": ["annotation_click_through_rate", "annotation_close_rate",
                    "annotation_impressions", "annotation_clickable_impressions",
                    "annotation_closable_impressions", "annotation_clicks",
                    "annotation_closes"],
    },

    # --- Playlists
    "playlist_basic_a2": {
        "priority": 15,
        "label": "Playlist user activity",
        "dimensions": ["date", "channel_id", "playlist_id", "video_id",
                       "live_or_on_demand", "subscribed_status", "country_code"],
        "metrics": ["views", "engaged_views", "watch_time_minutes",
                    "average_view_duration_seconds", "playlist_starts",
                    "playlist_saves_added", "playlist_saves_removed"],
    },
    "playlist_traffic_source_a2": {
        "priority": 16,
        "label": "Playlist traffic sources",
        "dimensions": ["date", "channel_id", "playlist_id", "video_id",
                       "live_or_on_demand", "subscribed_status", "country_code",
                       "traffic_source_type", "traffic_source_detail"],
        "metrics": ["views", "engaged_views", "watch_time_minutes",
                    "average_view_duration_seconds", "playlist_starts",
                    "playlist_saves_added", "playlist_saves_removed"],
    },
    "playlist_playback_location_a2": {
        "priority": 17,
        "label": "Playlist playback locations",
        "dimensions": ["date", "channel_id", "playlist_id", "video_id",
                       "live_or_on_demand", "subscribed_status", "country_code",
                       "playback_location_type", "playback_location_detail"],
        "metrics": ["views", "engaged_views", "watch_time_minutes",
                    "average_view_duration_seconds", "playlist_starts",
                    "playlist_saves_added", "playlist_saves_removed"],
    },
    "playlist_device_os_a2": {
        "priority": 18,
        "label": "Playlist device and operating system",
        "dimensions": ["date", "channel_id", "playlist_id", "video_id",
                       "live_or_on_demand", "subscribed_status", "country_code",
                       "device_type", "operating_system"],
        "metrics": ["views", "engaged_views", "watch_time_minutes",
                    "average_view_duration_seconds", "playlist_starts",
                    "playlist_saves_added", "playlist_saves_removed"],
    },
    "playlist_combined_a2": {
        "priority": 19,
        "label": "Playlist combined",
        "dimensions": ["date", "channel_id", "playlist_id", "video_id",
                       "live_or_on_demand", "subscribed_status", "country_code",
                       "playback_location_type", "traffic_source_type",
                       "device_type", "operating_system"],
        "metrics": ["views", "engaged_views", "watch_time_minutes",
                    "average_view_duration_seconds", "playlist_starts",
                    "playlist_saves_added", "playlist_saves_removed"],
    },
    "playlist_province_a2": {
        "priority": 20,
        "label": "Playlist activity by US province",
        "dimensions": ["date", "channel_id", "playlist_id", "video_id",
                       "live_or_on_demand", "subscribed_status", "country_code",
                       "province_code"],
        "metrics": ["views", "engaged_views", "watch_time_minutes",
                    "average_view_duration_seconds", "playlist_starts",
                    "playlist_saves_added", "playlist_saves_removed"],
    },
}

# Reports worth pulling first if you ever need a fast partial run.
PRIORITY_REPORTS = ["channel_reach_basic_a1", "channel_basic_a3",
                    "channel_traffic_source_a3"]


def ordered_report_ids():
    """All report IDs, in scheduling/collection priority order."""
    return [rid for rid, _ in sorted(CHANNEL_REPORTS.items(),
                                     key=lambda kv: kv[1]["priority"])]


def label_for(report_id):
    meta = CHANNEL_REPORTS.get(report_id)
    return meta["label"] if meta else report_id
