import asyncio
import logging
from pathlib import Path
from manager.config_manager import ConfigManager
from strategy_executor import StrategyExecutor
from test_order_executor import OrderExecutor
from strategy_logics.maker_strategy import MakerStrategy
from strategy_logics.maker_strategy_2 import MakerStrategy2
from data_publisher_new import WooXStagingAPI

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger("TradingSystem")

    try:
        # 初始化配置管理器
        config_manager = ConfigManager()
        main_config = config_manager.get_main_config()
        if not main_config:
            raise ValueError("Failed to load main configuration")
        
        # 獲取配置值
        exchange_config = main_config.get('exchange', {})
        redis_config = main_config.get('redis', {})
        
        # 驗證必要的配置項
        required_configs = ['app_id', 'api_key', 'api_secret']
        missing_configs = [cfg for cfg in required_configs if cfg not in exchange_config]
        if missing_configs:
            raise ValueError(f"Missing required configurations: {missing_configs}")
        
        # 初始化組件
        components = {}
        try:
            components['data_publisher'] = WooXStagingAPI(
                app_id=exchange_config['app_id'],
                api_key=exchange_config['api_key'],
                api_secret=exchange_config['api_secret'],
                redis_host=redis_config.get('host', 'localhost'),
                redis_port=redis_config.get('port', 6379),
                simulator_mode=True
            )
            # strategy executor
            components['strategy_executor'] = StrategyExecutor(
                redis_url=f"redis://{redis_config.get('host', 'localhost')}:{redis_config.get('port', 6379)}"
            )
            # order executor
            components['order_executor'] = OrderExecutor(
                api_key=exchange_config['api_key'],
                api_secret=exchange_config['api_secret'],
                redis_url=f"redis://{redis_config.get('host', 'localhost')}:{redis_config.get('port', 6379)}",
                simulator_mode=True
            )
            
            # 載入 cta_strategy
            # strategy_config = config_manager.get_strategy_config('cta_strategy')
            # if not strategy_config:
            #     raise ValueError("Failed to load strategy configuration")
            
            # # 可將策略加在這
            # await components['strategy_executor'].add_strategy(
            #     strategy_class=CTAStrategy,
            #     config=strategy_config
            # )

            # 策略2
            # await components['strategy_executor'].add_strategy(
            #     strategy_class=TestStrategy,
            #     config=strategy_config
            # )
            
            # 測試策略
            # strategy_config_2 = config_manager.get_strategy_config('test_limit_strategy')
            # if not strategy_config_2:
            #     raise ValueError("Failed to load strategy configuration")
            # await components['strategy_executor'].add_strategy(
            #     strategy_class=TestLimitStrategy,
            #     config=strategy_config_2
            # )

            # 載入 AvMM 
            # strategy_config_3 = config_manager.get_strategy_config('AvellanedaMMv2_strategy')
            # if not strategy_config_3:

            # 添加策略
            strategy_config = config_manager.get_strategy_config('maker_strategy_2')
            if not strategy_config:
                raise ValueError("Failed to load strategy configuration")
            
            # 可將策略加在這
            await components['strategy_executor'].add_strategy(
                strategy_class=MakerStrategy,
                config=strategy_config
            )
            
            # 訂閱的市場和私有頻道

            subscsribe_config = strategy_config.get('subscription_params', {})
            market_channels, private_channels = generate_channels(subscsribe_config)
            
            # 創建並運行所有任務
            logger.info("Starting all system components...")
            tasks = [
                asyncio.create_task(components['data_publisher'].start(
                    symbol=subscsribe_config['symbol'],
                    market_config=subscsribe_config['market_config'],
                    private_config=subscsribe_config['private_config']
                )),
                asyncio.create_task(components['strategy_executor'].start(
                    market_channels=market_channels,
                    private_channels=private_channels
                )),
                asyncio.create_task(components['order_executor'].start(
                    signal_channel="trading_signals",
                    execution_channel="execution_reports"
                ))
            ]
            
            await asyncio.gather(*tasks)
            
        except Exception as e:
            logger.error(f"Error initializing components: {e}")
            raise
            
    except Exception as e:
        logger.error(f"Error in main: {e}")
    finally:
        # 清理資源
        if 'components' in locals():
            cleanup_tasks = []
            if 'data_publisher' in components:
                cleanup_tasks.append(asyncio.create_task(
                    components['data_publisher'].close_connections()
                ))
            if 'strategy_executor' in components:
                cleanup_tasks.append(asyncio.create_task(
                    components['strategy_executor'].cleanup()
                ))
            if 'order_executor' in components:
                cleanup_tasks.append(asyncio.create_task(
                    components['order_executor'].stop()
                ))
                
            if cleanup_tasks:
                await asyncio.gather(*cleanup_tasks)
        logger.info("System shutdown complete")

def generate_channels(config):
    # Initialize the lists for market_channels and private_channels
    market_channels = []
    private_channels = []
    
    # Extract symbol and market_config from the config
    symbol = config['symbol']
    market_config = config['market_config']
    private_config = config['private_config']
    
    # For market_config, add entries to market_channels based on enabled data types
    for data_type, enabled in market_config.items():
        if enabled:  # If the data type is enabled (True)
            market_channels.append(f"{symbol}-{data_type}")
    
    # For private_config, add entries to private_channels based on enabled data types
    for data_type, enabled in private_config.items():
        if enabled:  # If the data type is enabled (True)
            private_channels.append(f"{data_type}")
    
    return market_channels, private_channels
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
    except Exception as e:
        print(f"Program error: {str(e)}")