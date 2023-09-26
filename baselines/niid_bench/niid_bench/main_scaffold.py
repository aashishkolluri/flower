import flwr as fl
import hydra
from hydra.utils import instantiate
from hydra.core.hydra_config import HydraConfig
from omegaconf import DictConfig, OmegaConf

from niid_bench.dataset import load_datasets
from niid_bench.client_scaffold import gen_client_fn
import niid_bench.server_scaffold as server
import os

@hydra.main(config_path="conf", config_name="scaffold_base", version_base=None)
def main(cfg: DictConfig) -> None:
    """Run the baseline.

    Parameters
    ----------
    cfg : DictConfig
        An omegaconf object that stores the hydra config.
    """
    # 1. Print parsed config
    print(OmegaConf.to_yaml(cfg))

    # 2. Prepare your dataset
    # here you should call a function in datasets.py that returns whatever is needed to:
    # (1) ensure the server can access the dataset used to evaluate your model after
    # aggregation
    # (2) tell each client what dataset partitions they should use (e.g. a this could
    # be a location in the file system, a list of dataloader, a list of ids to extract
    # from a dataset, it's up to you)
    trainloaders, valloaders, testloader = load_datasets(
        config=cfg.dataset,
        num_clients=cfg.num_clients,
        val_ratio=cfg.dataset.val_split,
        seed=cfg.dataset.seed,
    )

    save_path = HydraConfig.get().runtime.output_dir
    print("Outputs and Client cvs for scaffold saved to: ",  save_path)

    client_cv_dir = os.path.join(save_path, "client_cvs")
    # 3. Define your clients
    # Define a function that returns another function that will be used during
    # simulation to instantiate each individual client
    
    client_fn = gen_client_fn(
        trainloaders,
        valloaders,
        num_epochs=cfg.num_epochs,
        learning_rate=cfg.learning_rate,
        model=cfg.model,
        momentum=cfg.momentum,
        weight_decay=cfg.weight_decay,
        client_cv_dir=client_cv_dir,
    )

    device = cfg.server_device
    evaluate_fn = server.gen_evaluate_fn(testloader, device=device, model=cfg.model)

    # 4. Define your strategy
    # pass all relevant argument (including the global dataset used after aggregation,
    # if needed by your method.)
    # strategy = instantiate(cfg.strategy, <additional arguments if desired>)
    strategy = instantiate(
        cfg.strategy,
        evaluate_fn=evaluate_fn,
    )

    # 5. Start Simulation
    # history = fl.simulation.start_simulation(<arguments for simulation>)
    history = fl.simulation.start_simulation(
        server=server.ScaffoldServer(strategy=strategy, model=cfg.model),
        client_fn=client_fn,
        num_clients=cfg.num_clients,
        config=fl.server.ServerConfig(num_rounds=cfg.num_rounds),
        client_resources={
            "num_cpus": cfg.client_resources.num_cpus,
            "num_gpus": cfg.client_resources.num_gpus,
        },
        strategy=strategy,
    )

    print(history)
    print("Outputs and Client cvs for scaffold saved to: ",  save_path)
    

    # 6. Save your results
    # Here you can save the `history` returned by the simulation and include
    # also other buffers, statistics, info needed to be saved in order to later
    # on generate the plots you provide in the README.md. You can for instance
    # access elements that belong to the strategy for example:
    # data = strategy.get_my_custom_data() -- assuming you have such method defined.
    # Hydra will generate for you a directory each time you run the code. You
    # can retrieve the path to that directory with this:
    # save_path = HydraConfig.get().runtime.output_dir


if __name__ == "__main__":
    main()