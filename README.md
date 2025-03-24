RE4SC: A tool for reordering bytecode-level granular blocks to repair reentrancy vulnerabilities
We propose the first runtime enforcement framework for vulnerable smart contracts, named as RE4SC. It can repair smart contracts of Blockchain-based crowdsourcing logistics at runtime, which contains two components: granularity segmentation off-Blockchain and granular block reordering on-Blockchain. At the off-Blockchain level, the bytecode segmentation method is designed to refine basic blocks in the control flow graph (CFG) as granular blocks, which is based on stack state and syntactic structure pattern. Then, the Granular Block Relationship Tree (GBRT) is constructed from CFG, and the reverse search algorithm based on data item is designed to ensure data dependency consistency. At the on-Blockchain level, according to security properties and key granular blocks, the depth-first reordering algorithm of granular block is designed to reorder state variable for repairing reentrancy vulnerabilities, which is based on the composite semantics off-Blockchain.
