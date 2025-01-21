import os
import json
import time
from typing import Dict, Set
from datetime import datetime
from discord_webhook import DiscordWebhook, DiscordEmbed

class TokenDetailsMonitor:
    def __init__(self):
        self.token_details_dir = "token_details"
        # Separate price fields that change frequently from those we want to monitor
        self.ignored_fields = {'markPx', 'prevDayPx'}  # Remove midPx from ignored fields
        self.price_transition_states = {}  # Track trading status of tokens
        # Discord webhook for notifications
        self.discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL', 
            "https://discord.com/api/webhooks/1331306235374473316/6aSHuNJU-azQV7Of9-vGgKwafsOAIPjJkkpFpUYMDsiC03URbanrWh2YVLukp_chm2Fv")
        
        # Store previous state of token details
        self.previous_states: Dict[str, Dict] = {}
        self.load_initial_states()

    def load_initial_states(self):
        """Load the initial state of all token detail files"""
        for filename in os.listdir(self.token_details_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(self.token_details_dir, filename)
                try:
                    with open(file_path, 'r') as f:
                        token_data = json.load(f)
                        # Store initial trading status
                        self.price_transition_states[filename] = token_data.get('midPx') is not None
                        # Remove ignored fields from stored state
                        cleaned_data = {k: v for k, v in token_data.items() 
                                     if k not in self.ignored_fields}
                        self.previous_states[filename] = cleaned_data
                except Exception as e:
                    print(f"Error loading initial state for {filename}: {e}")

    def format_value(self, value) -> str:
        """Format value for display in Discord message"""
        if isinstance(value, (int, float)):
            return f"{value:,}"
        return str(value)

    def send_discord_alert(self, token_id: str, changes: Dict[str, tuple]):
        """Send a Discord alert for token detail changes"""
        if not self.discord_webhook_url:
            return

        try:
            webhook = DiscordWebhook(url=self.discord_webhook_url)
            
            embed = DiscordEmbed(
                title="🔄 Token Details Changed",
                description=f"Changes detected for token: **{token_id}**",
                color="03b2f8"
            )
            
            # Add each change as a field
            for field, (old_value, new_value) in changes.items():
                formatted_old = self.format_value(old_value)
                formatted_new = self.format_value(new_value)
                
                embed.add_embed_field(
                    name=field,
                    value=f"Old: {formatted_old}\nNew: {formatted_new}",
                    inline=False
                )
            
            embed.set_timestamp()
            embed.set_footer(text="HyperLiquid Token Monitor")
            
            webhook.add_embed(embed)
            webhook.execute()
            
        except Exception as e:
            print(f"Error sending Discord alert: {e}")

    def send_trading_status_alert(self, token_id: str, price: float):
        """Send a Discord alert when a token becomes tradeable"""
        if not self.discord_webhook_url:
            return

        try:
            webhook = DiscordWebhook(url=self.discord_webhook_url)
            
            embed = DiscordEmbed(
                title="🚀 Token Now Tradeable",
                description=f"Token **{token_id}** has become tradeable!",
                color="00ff00"  # Green color
            )
            
            embed.add_embed_field(
                name="Initial Price",
                value=f"${self.format_value(price)}",
                inline=True
            )
            
            embed.set_timestamp()
            embed.set_footer(text="HyperLiquid Token Monitor")
            
            webhook.add_embed(embed)
            webhook.execute()
            
        except Exception as e:
            print(f"Error sending trading status alert: {e}")

    def send_new_token_alert(self, token_id: str, token_data: Dict):
        """Send a Discord alert when a new token file is detected"""
        if not self.discord_webhook_url:
            return

        try:
            webhook = DiscordWebhook(url=self.discord_webhook_url)
            
            embed = DiscordEmbed(
                title="📝 New Token Added",
                description=f"New token file detected: **{token_id}**",
                color="ff9900"  # Orange color
            )
            
            # Add initial trading status
            is_trading = token_data.get('midPx') is not None
            trading_status = "Tradeable" if is_trading else "Not tradeable"
            embed.add_embed_field(
                name="Trading Status",
                value=trading_status,
                inline=True
            )
            
            if is_trading:
                embed.add_embed_field(
                    name="Initial Price",
                    value=f"${self.format_value(token_data.get('midPx'))}",
                    inline=True
                )
            
            embed.set_timestamp()
            embed.set_footer(text="HyperLiquid Token Monitor")
            
            webhook.add_embed(embed)
            webhook.execute()
            
        except Exception as e:
            print(f"Error sending new token alert: {e}")

    def check_for_changes(self):
        """Check for changes in token detail files"""
        for filename in os.listdir(self.token_details_dir):
            if not filename.endswith('.json'):
                continue

            file_path = os.path.join(self.token_details_dir, filename)
            try:
                with open(file_path, 'r') as f:
                    current_data = json.load(f)
                    
                    # Check if this is a new file
                    if filename not in self.previous_states:
                        token_id = filename.replace('.json', '')
                        print(f"New token file detected: {token_id}")
                        self.send_new_token_alert(token_id, current_data)
                    
                    # Check for trading status change
                    was_trading = self.price_transition_states.get(filename, False)
                    is_trading = current_data.get('midPx') is not None
                    
                    if not was_trading and is_trading:
                        # Token has become tradeable
                        token_id = filename.replace('.json', '')
                        print(f"Token {token_id} is now tradeable at price: {current_data.get('midPx')}")
                        self.send_trading_status_alert(token_id, current_data.get('midPx'))
                    
                    # Update trading status
                    self.price_transition_states[filename] = is_trading
                    
                    # Remove ignored fields for regular change detection
                    cleaned_current = {k: v for k, v in current_data.items() 
                                    if k not in self.ignored_fields}
                    
                    # Get previous state or empty dict if new file
                    previous_data = self.previous_states.get(filename, {})
                    
                    # Track changes (excluding price changes if already trading)
                    changes = {}
                    
                    # Check for changed or new fields
                    for key, value in cleaned_current.items():
                        if key == 'midPx' and was_trading:
                            continue  # Skip midPx changes for already trading tokens
                        if key not in previous_data:
                            changes[key] = (None, value)  # New field
                        elif previous_data[key] != value:
                            changes[key] = (previous_data[key], value)  # Changed field
                    
                    # Check for removed fields
                    for key in previous_data:
                        if key not in cleaned_current:
                            changes[key] = (previous_data[key], None)  # Removed field
                    
                    # If changes detected, send alert
                    if changes:
                        token_id = filename.replace('.json', '')
                        print(f"Changes detected for {token_id}:")
                        for field, (old, new) in changes.items():
                            print(f"  {field}: {old} -> {new}")
                        self.send_discord_alert(token_id, changes)
                    
                    # Update stored state
                    self.previous_states[filename] = cleaned_current
                    
            except Exception as e:
                print(f"Error processing {filename}: {e}")

def main():
    monitor = TokenDetailsMonitor()
    print("Starting Token Details monitor...")
    
    while True:
        try:
            monitor.check_for_changes()
            time.sleep(1)  # Check every second
        except KeyboardInterrupt:
            print("\nMonitor stopped by user")
            break
        except Exception as e:
            print(f"Error in main loop: {e}")
            time.sleep(60)  # Wait before retrying

if __name__ == "__main__":
    main() 