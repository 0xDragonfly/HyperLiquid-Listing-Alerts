import requests
import time
from typing import Dict, Set
import json
from datetime import datetime
import os
from tqdm import tqdm
from discord_webhook import DiscordWebhook, DiscordEmbed
import dateutil.parser

class HyperLiquidMonitor:
    def __init__(self):
        self.base_url = "https://api.hyperliquid.xyz/info"
        self.cache_file = "hyperliquid_pairs_cache.json"
        self.token_details_dir = "token_details"
        # Load Discord webhook URLs from environment variables
        # self.discord_webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
        # self.system_webhook_url = os.getenv('SYSTEM_WEBHOOK_URL')
        self.discord_webhook_url = "https://discord.com/api/webhooks/1331158677750808577/7XqKEQslL_4cuK3syW4lulaqj4x0qi5LBR-bwrn9thLYss4condu-Q3Lpo-Pii5tVwce"
        self.system_webhook_url = "https://discord.com/api/webhooks/1331162793902342215/Zu3hvnKvdVdzrDfAi9729J_sQynsy9AaDLlEzcZtznS64O3r77EPDHvSTj5FMHALN0Z_"
        if not self.discord_webhook_url:
            print("Warning: DISCORD_WEBHOOK_URL environment variable not set")
        if not self.system_webhook_url:
            print("Warning: SYSTEM_WEBHOOK_URL environment variable not set")
        
        # Create token details directory if it doesn't exist
        os.makedirs(self.token_details_dir, exist_ok=True)
        self.known_pairs: Set[str] = self.load_cache()
        self.pairs_with_liquidity: Set[str] = set()
        
    def load_cache(self) -> Set[str]:
        """Load known pairs from cache file"""
        try:
            with open(self.cache_file, 'r') as f:
                return set(json.load(f))
        except FileNotFoundError:
            return set()
            
    def save_cache(self):
        """Save known pairs to cache file"""
        with open(self.cache_file, 'w') as f:
            json.dump(list(self.known_pairs), f)
            
    def fetch_spot_markets(self) -> Dict:
        """Fetch current spot market data from HyperLiquid"""
        payload = {
            "type": "spotMeta"
        }
        
        try:
            response = requests.post(self.base_url, json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching market data: {e}")
            return None

    def fetch_token_details(self, token_id: str) -> Dict:
        """Fetch detailed information about a specific token"""
        payload = {
            "type": "tokenDetails",
            "tokenId": token_id
        }
        
        try:
            time.sleep(1)
            response = requests.post(self.base_url, json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching token details for {token_id}: {e}")
            return None

    def save_token_details(self, token_id: str, details: Dict):
        """Save token details to a JSON file"""
        file_path = os.path.join(self.token_details_dir, f"{token_id}.json")
        try:
            with open(file_path, 'w') as f:
                json.dump(details, f, indent=4)
        except Exception as e:
            print(f"Error saving token details for {token_id}: {e}")

    def check_for_updates(self):
        """Check for new pairs and liquidity changes"""
        market_data = self.fetch_spot_markets()
        
        if not market_data:
            return
            
        current_pairs = set()
        
        # Process market data
        for asset in tqdm(market_data.get('tokens', []), desc="Processing assets"):
            pair_name = asset.get('name')
            token_id = asset.get('tokenId')
            current_pairs.add(pair_name)
            
            # If this is a new pair, fetch and store token details
            if pair_name not in self.known_pairs and token_id:
                token_details = self.fetch_token_details(token_id)
                if token_details:
                    self.save_token_details(token_id, token_details)
                    self.notify_new_pair(pair_name, token_details)
        
        # Update stored state
        self.known_pairs = current_pairs
        self.save_cache()

    def send_discord_alert(self, pair: str, token_details: Dict = None):
        """Send a formatted Discord alert for new pairs"""
        if not self.discord_webhook_url:
            return

        try:
            webhook = DiscordWebhook(url=self.discord_webhook_url)
            
            # Create embed
            embed = DiscordEmbed(
                title="🚨 New Spot Pair Listed on HyperLiquid",
                description=f"New trading pair detected: **{pair}**",
                color="03b2f8"  # Light blue color
            )
            
            # Add timestamp
            embed.set_timestamp()
            
            # Add token details if available
            if token_details:
                # Format numbers with commas, handle None values
                def format_number(value, is_price=False):
                    if value is None:
                        return "N/A"
                    try:
                        num = float(value)
                        if is_price:
                            return "${:,.2f}".format(num)
                        return "{:,}".format(num)
                    except (ValueError, TypeError):
                        return "N/A"
                
                total_supply = format_number(token_details.get('totalSupply'))
                circ_supply = format_number(token_details.get('circulatingSupply'))
                price = format_number(token_details.get('midPx'), is_price=True)
                
                # Add fields
                embed.add_embed_field(name="Total Supply", value=total_supply, inline=True)
                embed.add_embed_field(name="Circulating Supply", value=circ_supply, inline=True)
                embed.add_embed_field(name="Current Price", value=price, inline=True)
                
                # Add deploy time if available
                deploy_time = token_details.get('deployTime')
                if deploy_time:
                    try:
                        # Parse ISO format datetime string
                        deploy_datetime = dateutil.parser.parse(deploy_time)
                        embed.add_embed_field(
                            name="Deploy Time", 
                            value=deploy_datetime.strftime("%Y-%m-%d %H:%M:%S UTC"),
                            inline=False
                        )
                    except Exception as e:
                        print(f"Error parsing deploy time: {e}")
                        embed.add_embed_field(name="Deploy Time", value="N/A", inline=False)
            
            # Add footer
            embed.set_footer(text="HyperLiquid Monitor")
            
            # Add embed to webhook
            webhook.add_embed(embed)
            webhook.execute()
            
        except Exception as e:
            print(f"Error sending Discord alert: {e}")

    def notify_new_pair(self, pair: str, token_details: Dict = None):
        """Notify when a new pair is added with additional details"""
        # Console notification
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] New pair detected: {pair}")
        if token_details:
            print(f"Token Details:")
            print(f"  Total Supply: {token_details.get('totalSupply')}")
            print(f"  Circulating Supply: {token_details.get('circulatingSupply')}")
            print(f"  Current Price: {token_details.get('midPx')} USDC")
            print(f"  Deploy Time: {token_details.get('deployTime')}")
        
        # Send Discord alert
        self.send_discord_alert(pair, token_details)

    def notify_new_liquidity(self, pair: str):
        """Notify when new liquidity is added to an existing pair"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] New liquidity detected for pair: {pair}")

    def send_system_alert(self, error_message: str):
        """Send system alert to the monitoring Discord channel"""
        if not self.system_webhook_url:
            return

        try:
            webhook = DiscordWebhook(url=self.system_webhook_url)
            
            embed = DiscordEmbed(
                title="⚠️ HyperLiquid Monitor Alert",
                description=f"System Error Detected",
                color="ff0000"  # Red color for errors
            )
            
            embed.add_embed_field(
                name="Error Details", 
                value=f"```{error_message}```",
                inline=False
            )
            
            embed.add_embed_field(
                name="Timestamp", 
                value=datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
                inline=False
            )
            
            embed.set_footer(text="HyperLiquid Monitor - System Alert")
            
            webhook.add_embed(embed)
            webhook.execute()
            
        except Exception as e:
            print(f"Error sending system alert: {e}")

def main():
    monitor = HyperLiquidMonitor()
    print("Starting HyperLiquid market monitor...")
    
    while True:
        try:
            monitor.check_for_updates()
            time.sleep(0.5)  # Check every minute
        except KeyboardInterrupt:
            print("\nMonitor stopped by user")
            monitor.send_system_alert("Monitor stopped by user")
            break
        except Exception as e:
            error_msg = f"Error in main loop: {e}"
            print(error_msg)
            monitor.send_system_alert(error_msg)
            time.sleep(60)  # Wait before retrying

if __name__ == "__main__":
    main() 