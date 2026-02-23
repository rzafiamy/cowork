import sys
from pathlib import Path

# Add CLI dir to sys path for imports
project_root = Path(__file__).parent.parent
cli_dir = project_root / "cli"
sys.path.insert(0, str(cli_dir))

from cowork.tools.builtin.cron import CronScheduleTool
from cowork.cron import CronManager, CRON_FILE

def test_cron_schedule_tool_execution():
    # Ensure a clean state for testing if CRON_FILE exists
    if CRON_FILE.exists():
        CRON_FILE.unlink()
    
    tool = CronScheduleTool()
    mgr = CronManager()
    
    # Verify initial state
    assert len(mgr.list_all()) == 0
    
    # Execute the tool
    prompt = "Test periodic task"
    schedule_type = "daily"
    schedule_value = "09:00"
    
    result = tool.execute(prompt, schedule_type, schedule_value)
    
    # Verify output
    assert "✅ Task scheduled" in result
    assert "daily @ 09:00" in result
    
    # Verify persistence
    mgr_new = CronManager() # Reload from disk
    jobs = mgr_new.list_all()
    assert len(jobs) == 1
    job = jobs[0]
    assert job.prompt == prompt
    assert job.schedule_type == schedule_type
    assert job.schedule_value == schedule_value
    
    # Cleanup
    if CRON_FILE.exists():
        CRON_FILE.unlink()

if __name__ == "__main__":
    try:
        test_cron_schedule_tool_execution()
        print("✅ test_cron_schedule_tool_execution passed!")
    except Exception as e:
        print(f"❌ test_cron_schedule_tool_execution failed: {e}")
        sys.exit(1)
