import sys
import json
from summarizer.post_call import summarize_transcript
from summarizer.store import store_transcript, store_summary


def process_meeting(meeting_id: str, transcript_path: str, metadata: dict = None) -> dict:
    metadata = metadata or {}

    with open(transcript_path, "r") as f:
        transcript = f.read()

    print(f"Summarizing meeting {meeting_id}...")
    summary_data = summarize_transcript(transcript)

    print("Storing transcript...")
    chunk_count = store_transcript(meeting_id, transcript, metadata)

    print("Storing summary...")
    store_summary(meeting_id, summary_data, metadata)

    print(f"Done. {chunk_count} transcript chunks + 1 summary indexed.\n")
    print(json.dumps(summary_data, indent=2))

    return summary_data


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m summarizer.run <meeting_id> <transcript_file>")
        sys.exit(1)

    process_meeting(sys.argv[1], sys.argv[2])