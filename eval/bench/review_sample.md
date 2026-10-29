# GeoRAG-Bench spot-check sample

A random 10 % of the generated questions with their gold passages. Mark each as OK / ambiguous / wrong.

## qa-remote_sensing-020

**Q:** Which satellites provide the imagery used in the deep learning model for deforestation and burned area detection in the Amazon?

**A:** Sentinel, Landsat, VIIRS, and MODIS

> *Rapid Deforestation and Burned Area Detection using Deep Multimodal Learning on Satellite Imagery* — Deforestation estimation and fire detection in the Amazon forest poses a significant challenge due to the vast size of the area and the limited accessibility. However, these are crucial problems that lead to severe environmental consequences, including climate change, global warming, and biodiversity loss. To effectively address this problem, multimodal satellite imagery and remote sensing offer a promising solution for estimating deforestation and detecting wildfire in the Amazonia region. This research paper introduces a new curated dataset and a deep learning-based approach to solve these problems using convolutional neural networks (CNNs) and comprehensive data processing techniques. Our

Verdict: ☐ OK ☐ ambiguous ☐ wrong

## qa-digital_twin-031

**Q:** What mobility model is used to characterize users' movements in the H-AP deployment scheme?

**A:** a grid based city streets mobility model

> *H-AP Deployment for Joint Wireless Information and Energy Transfer in Smart Cities* — With the wireless communication being more various in the future, it's becoming challenging to prolong the lifetime of many battery powered devices, since frequently replacing their batteries is a cumbersome job. An hybrid access point (H-AP) is capable of simultaneously operating wireless information transfer (WIT) and wireless energy transfer (WET) by exploiting the radio frequency (RF) signals. By jointly considering both the mobility of the user and the popularity of the sites, we focus on the design of the H-AP's deployment scheme. Specifically, a mobility model of the grid based city streets is exploited for characterising the users' movements. Based on this mobility model, the impact 

Verdict: ☐ OK ☐ ambiguous ☐ wrong

## qa-digital_twin-019

**Q:** What 3D autoencoder model is used to generate latent representations of buildings from a LoD 2 CityGML dataset?

**A:** FoldingNet

> *FoldingNet Autoencoder model to create a geospatial grouping of CityGML building dataset* — Explainable numerical representations or latent information of otherwise complex datasets are more convenient to analyze and study. These representations assist in identifying clusters and outliers, assess similar data points, and explore and interpolate data. Dataset of three-dimensional (3D) building models possesses inherent complexity in various footprint shapes, distinct roof types, walls, height, and volume. Traditionally, grouping similar buildings or 3D shapes requires matching their known properties and shape metrics with each other. However, this requires obtaining a plethora of such properties to calculate similarity. This study, in contrast, utilizes an autoencoder to compute the

Verdict: ☐ OK ☐ ambiguous ☐ wrong

## qa-gis-033

**Q:** What percentage of Starlink terminals experienced substantial performance degradation during severe weather events in the contiguous United States?

**A:** more than 55%

> *Mapping the Storm: Geospatial Impacts of Severe Weather on LEO Network Performance* — LEO satellite constellations, led by deployments such as Starlink, are playing an increasingly pivotal role in enabling global broadband connectivity. However, the reliability and performance of these space-based networks are highly sensitive to environmental dynamics, particularly localized weather phenomena that exhibit strong spatio-temporal variability. In this study, we present a continental-scale geospatial analysis of weather-induced performance degradation in the Starlink LEO network, with a focus on the contiguous United States. Leveraging a unique dataset comprising more than 870,000 terminal hours of minute-level telemetry from 1,292 Starlink terminals, we integrate high-resolutio

Verdict: ☐ OK ☐ ambiguous ☐ wrong

## qa-lidar-014

**Q:** What coordinate system is used in the voxelization method for LiDAR point clouds to better represent their geometry?

**A:** cylindrical coordinates

> *Cylindrical coordinates for LiDAR point cloud compression* — We present an efficient voxelization method to encode the geometry and attributes of 3D point clouds obtained from autonomous vehicles. Due to the circular scanning trajectory of sensors, the geometry of LiDAR point clouds is inherently different from that of point clouds captured from RGBD cameras. Our method exploits these specific properties to representing points in cylindrical coordinates instead of conventional Cartesian coordinates. We demonstrate thatRegion Adaptive Hierarchical Transform (RAHT) can be extended to this setting, leading to attribute encoding based on a volumetric partition in cylindrical coordinates. Experimental results show that our proposed voxelization outperforms

Verdict: ☐ OK ☐ ambiguous ☐ wrong

## qa-digital_twin-034

**Q:** What AI-based method is used to generate synthetic cybersecurity datasets for smart city research?

**A:** generative artificial intelligence models

> *Bridging the Smart City Cybersecurity Data Gap Through AI-Driven Synthetic Dataset Generation* — Smart cities rely on interconnected cyber-physical systems that integrate sensors, IoT devices, cloud platforms, and AI-driven services and decision-making. While these systems enhance city services, they also introduce complex cybersecurity challenges due to their large attack surfaces, heterogeneous data flows, and evolving threat vectors. Developing and validating cybersecurity tools for smart cities requires high-quality datasets that accurately represent real operational conditions. However, real-world datasets are often incomplete, contain privacy-sensitive data, are difficult to access, or lack sufficient malicious activity to support tool development. This research addresses this cri

Verdict: ☐ OK ☐ ambiguous ☐ wrong

## qa-digital_twin-001

**Q:** What is the common technique used to improve data output quality or extract knowledge from raw data in smart city applications?

**A:** data fusion

> *A Survey of Data Fusion in Smart City Applications* — The advancement of various research sectors such as Internet of Things (IoT), Machine Learning, Data Mining, Big Data, and Communication Technology has shed some light in transforming an urban city integrating the aforementioned techniques to a commonly known term - Smart City. With the emergence of smart city, plethora of data sources have been made available for wide variety of applications. The common technique for handling multiple data sources is data fusion, where it improves data output quality or extracts knowledge from the raw data. In order to cater evergrowing highly complicated applications, studies in smart city have to utilize data from various sources and evaluate their perfor

Verdict: ☐ OK ☐ ambiguous ☐ wrong

## qa-geo_cv-000

**Q:** What is the name of the pre-trained geospatial foundation model used in the FARM framework?

**A:** Prithvi-EO-2.0-600M

> *FARM: Fine-Tuning Geospatial Foundation Models for Intra-Field Crop Yield Regression* — Accurate and timely crop yield prediction is crucial for global food security and modern agricultural management. Traditional methods often lack the scalability and granularity required for precision farming. This paper introduces FARM: Fine-tuning Agricultural Regression Models, a deep learning framework designed for high-resolution, intra-field canola yield prediction. FARM leverages a pre-trained, large-scale geospatial foundation model (Prithvi-EO-2.0-600M) and adapts it for a continuous regression task, transforming multi-temporal satellite imagery into dense, pixel-level (30 m) yield maps. Evaluated on a comprehensive dataset from the Canadian Prairies, FARM achieves a Root Mean Square

Verdict: ☐ OK ☐ ambiguous ☐ wrong

## qa-digital_twin-028

**Q:** What type of information does the end-to-end IoT system extract from urban sound in residential areas?

**A:** The system extracts real-time urban sound metadata including sound type, location, duration, rate of occurrence, loudness, and azimuth of a dominant noise.

> *Extracting Urban Sound Information for Residential Areas in Smart Cities Using an End-to-End IoT System* — With rapid urbanization comes the increase of community, construction, and transportation noise in residential areas. The conventional approach of solely relying on sound pressure level (SPL) information to decide on the noise environment and to plan out noise control and mitigation strategies is inadequate. This paper presents an end-to-end IoT system that extracts real-time urban sound metadata using edge devices, providing information on the sound type, location and duration, rate of occurrence, loudness, and azimuth of a dominant noise in nine residential areas. The collected metadata on environmental sound is transmitted to and aggregated in a cloud-based platform to produce detailed de

Verdict: ☐ OK ☐ ambiguous ☐ wrong

## qa-gis-016

**Q:** What dataset was used to build cultural maps of Paris, Vienna, London, and New York?

**A:** A dataset of 5,000 streets across the cities of Paris, Vienna, London, and New York.

> *Cartographic Design of Cultural Maps* — Throughout history, maps have been used as a tool to explore cities. They visualize a city's urban fabric through its streets, buildings, and points of interest. Besides purely navigation purposes, street names also reflect a city's culture through its commemorative practices. Therefore, cultural maps that unveil socio-cultural characteristics encoded in street names could potentially raise citizens' historical awareness. But designing effective cultural maps is challenging, not only due to data scarcity but also due to the lack of effective approaches to engage citizens with data exploration. To address these challenges, we collected a dataset of 5,000 streets across the cities of Paris, Vi

Verdict: ☐ OK ☐ ambiguous ☐ wrong

## qa-digital_twin-035

**Q:** What is the primary goal of sensor-based systems in smart cities?

**A:** To provide essential services with minimal human intervention and operate in a self-organizing manner.

> *Smart Cities: The Hopes and Hypes* — Smart cities are being planned for several advanced applications and services for the inhabitants. Smart cities initiative promise many new services which are not possible in the traditional city frameworks. In the smart city framework, the basic aim is to provide all the essential services through sensor based systems which does not need much human intervention. This system is designed to operate on its own in a self-organizing manner. Therefore, the hopes are really big from the smart cities to enhance the quality of lives and the economy. However, some of the promises in the smart cities are very much over hyped. In this article, we analyse the realities of the smart cities and their prac

Verdict: ☐ OK ☐ ambiguous ☐ wrong

## qa-gis-003

**Q:** What satellite dataset is used to map atmospheric methane in the Bowen Basin, Queensland, Australia?

**A:** Sentinel 5P satellite data

> *Bayesian copula-based spatial random effects models for inference with complex spatial data* — In this article, we develop fully Bayesian, copula-based, spatial-statistical models for large, noisy, incomplete, and non-Gaussian spatial data. Our approach includes novel constructions of copulas that accommodate a spatial-random-effects structure, enabling low-rank representations and computationally efficient Bayesian inference. The spatial copula is used in a latent process model of the Bayesian hierarchical spatial-statistical model, and, conditional on the latent copula-based spatial process, the data model handles measurement errors and missing data. Our simulation studies show that a fully Bayesian approach delivers accurate and fast inference for both parameter estimation and spat

Verdict: ☐ OK ☐ ambiguous ☐ wrong

## cross-014

**Q:** How does the adversarial loss function applied to DeepLabV3+ improve building extraction from aerial imagery, and what is its impact on segmentation accuracy when compared to traditional per-pixel loss methods in the context of LiDAR-based LOD1 3D building modeling?

**A:** The adversarial loss function applied to DeepLabV3+ enhances building extraction from aerial imagery by learning both local and global contextual information, which refines building edges and improves structural accuracy without requiring post-processing like Conditional Random Fields. This results in a significant improvement in segmentation performance—achieving a relaxed F1 score of 95.59% on the Massachusetts buildings dataset, surpassing previous bests. In the context of LiDAR-based LOD1 3D building modeling, where accurate semantic segmentation is critical for extracting reliable building footprints and morphological features (such as area and wall surface), this improved segmentation accuracy directly translates to more precise height estimations and better quality 3D models, especially when using metrics like median and 90th percentile. Thus, the adversarial loss strengthens DeepLabV3+'s ability to produce accurate, context-aware segmentations that support high-fidelity LOD1 modeling.

> *Adversarial Loss for Semantic Segmentation of Aerial Imagery* — Automatic building extraction from aerial imagery has several applications in urban planning, disaster management, and change detection. In recent years, several works have adopted deep convolutional neural networks (CNNs) for building extraction, since they produce rich features that are invariant against lighting conditions, shadows, etc. Although several advances have been made, building extraction from aerial imagery still presents multiple challenges. Most of the deep learning segmentation methods optimize the per-pixel loss with respect to the ground truth without knowledge of the context. This often leads to imperfect outputs that may lead to missing or unrefined regions. In this work

> *LOD1 3D City Model from LiDAR: The Impact of Segmentation Accuracy on Quality of Urban 3D Modeling and Morphology Extraction* — Three-dimensional reconstruction of buildings, particularly at Level of Detail 1 (LOD1), plays a crucial role in various applications such as urban planning, urban environmental studies, and designing optimized transportation networks. This study focuses on assessing the potential of LiDAR data for accurate 3D building reconstruction at LOD1 and extracting morphological features from these models. Four deep semantic segmentation models, U-Net, Attention U-Net, U-Net3+, and DeepLabV3+, were used, applying transfer learning to extract building footprints from LiDAR data. The results showed that U-Net3+ and Attention U-Net outperformed the others, achieving IoU scores of 0.833 and 0.814, respec

Verdict: ☐ OK ☐ ambiguous ☐ wrong

## qa-digital_twin-000

**Q:** What machine learning model is used in iWatchRoad for real-time pothole detection?

**A:** Ultralytics You Only Look Once (YOLO) model

> *iWatchRoad: Scalable Detection and Geospatial Visualization of Potholes for Smart Cities* — Potholes on the roads are a serious hazard and maintenance burden. This poses a significant threat to road safety and vehicle longevity, especially on the diverse and under-maintained roads of India. In this paper, we present a complete end-to-end system called iWatchRoad for automated pothole detection, Global Positioning System (GPS) tagging, and real time mapping using OpenStreetMap (OSM). We curated a large, self-annotated dataset of over 7,000 frames captured across various road types, lighting conditions, and weather scenarios unique to Indian environments, leveraging dashcam footage. This dataset is used to fine-tune, Ultralytics You Only Look Once (YOLO) model to perform real time po

Verdict: ☐ OK ☐ ambiguous ☐ wrong

## qa-remote_sensing-026

**Q:** What satellite platform provides the multispectral high-frequency Earth Observation data used in the HighFM model?

**A:** Meteosat Second Generation (MSG)

> *HighFM: Towards a Foundation Model for Learning Representations from High-Frequency Earth Observation Data* — The increasing frequency and severity of climate related disasters have intensified the need for real time monitoring, early warning, and informed decision-making. Earth Observation (EO), powered by satellite data and Machine Learning (ML), offers powerful tools to meet these challenges. Foundation Models (FMs) have revolutionized EO ML by enabling general-purpose pretraining on large scale remote sensing datasets. However most existing models rely on high-resolution satellite imagery with low revisit rates limiting their suitability for fast-evolving phenomena and time critical emergency response. In this work, we present HighFM, a first cut approach towards a FM for high temporal resolutio

Verdict: ☐ OK ☐ ambiguous ☐ wrong

## qa-digital_twin-021

**Q:** What is the positive impact of using building information modeling technology in construction safety?

**A:** The positive impact of using building information modeling technology in construction safety is that it helps reduce financial losses and increases productivity by improving safety management.

> *Examining the position of building information modeling (BIM) technology in different dimensions of building smartness* — Due to the fact that the construction industry is one of the high-risk industries, it is inevitable to pay sufficient attention to the safety category in this industry. Currently, due to the development of modern technologies, the traditional methods used in safety management have given way to the mentioned technologies. Therefore, the use of modern technologies such as BIM can be a practical step in reducing financial losses while increasing productivity. The purpose of this research is to investigate the role and place of using building information modeling in different sectors, such as improving smartness, and safety, and its application in reducing energy consumption. Considering that a 

Verdict: ☐ OK ☐ ambiguous ☐ wrong

## qa-remote_sensing-019

**Q:** What satellite imagery modalities are used in the pretrained model for earth observation tasks?

**A:** Sentinel 2 RGB optical imagery, Sentinel 1 SAR radar amplitude and interferometric coherence

> *Fewshot learning on global multimodal embeddings for earth observation tasks* — In this work we pretrain a CLIP/ViT based model using three different modalities of satellite imagery across five AOIs covering over ~10\% of Earth's total landmass, namely Sentinel 2 RGB optical imagery, Sentinel 1 SAR radar amplitude and interferometric coherence. This model uses $\sim 250$ M parameters. Then, we use the embeddings produced for each modality with a classical machine learning method to attempt different downstream tasks for earth observation related to vegetation, built up surface, croplands and permanent water. We consistently show how we reduce the need for labeled data by 99\%, so that with ~200-500 randomly selected labeled examples (around 4K-10K km$^2$) we reach perfo

Verdict: ☐ OK ☐ ambiguous ☐ wrong

## qa-remote_sensing-009

**Q:** What method is used to adapt general-purpose vision-language models for multispectral and SAR image understanding?

**A:** LoRA adaptation of the language network and selected visual transformer blocks with rendered inputs consisting of five optical views and one SAR view.

> *Lightweight Adaptation of General-Purpose VLMs for Multispectral and SAR Image Understanding* — General-purpose vision-language models (VLMs) now support strong visual recognition, instruction following, and generation. However, most pretrained visual encoders are built around three-channel natural images and do not directly accommodate observations such as native multispectral measurements or synthetic aperture radar (SAR). Adapting VLMs to these sensors typically requires dedicated encoders and domain pretraining, slowing the reuse of stronger general-purpose checkpoints. We show that the multi-image interface of general-purpose VLMs offers a lightweight alternative. Our protocol renders each observation as five optical views and one SAR view, names them in the prompt, and adapts the

Verdict: ☐ OK ☐ ambiguous ☐ wrong

## qa-geo_cv-023

**Q:** What is the mean Intersection over Union (mIoU) achieved by fusing aerial and satellite images using the enhanced DeepLabV3+ architecture on the LandCover.ai and Sentinel 2 datasets?

**A:** 84.91%

> *Enhancing DeepLabV3+ to Fuse Aerial and Satellite Images for Semantic Segmentation* — Aerial and satellite imagery are inherently complementary remote sensing sources, offering high-resolution detail alongside expansive spatial coverage. However, the use of these sources for land cover segmentation introduces several challenges, prompting the development of a variety of segmentation methods. Among these approaches, the DeepLabV3+ architecture is considered as a promising approach in the field of single-source image segmentation. However, despite its reliable results for segmentation, there is still a need to increase its robustness and improve its performance. This is particularly crucial for multimodal image segmentation, where the fusion of diverse types of information is e

Verdict: ☐ OK ☐ ambiguous ☐ wrong

## cross-013

**Q:** How can the semantic alignment capabilities of CLIP, as utilized in structural damage assessment through Vision-Language Models (VLMs), be leveraged to improve cartographic reasoning in map visual question-answering tasks evaluated by FRIEDA?

**A:** The semantic alignment capabilities of CLIP, used in Passage A for reference-free evaluation of building damage severity via VLMs, can inform and enhance cartographic reasoning in FRIEDA by enabling more accurate cross-modal understanding between map elements (e.g., symbols, labels, geometries) and their spatial or topological relationships. Specifically, CLIP's ability to align visual features with textual descriptions allows models to interpret legend symbology, match geographic text labels with corresponding regions, and reason about directional or metric relations across maps—tasks central to FRIEDA’s multi-step cartographic reasoning benchmarks. By integrating CLIP-based alignment into VLMs for map interpretation, models can better ground spatial inferences in both visual and textual context, thereby improving performance on topological, metric, and directional reasoning tasks that currently remain poorly addressed by existing LVLMs.

> *FRIEDA: Benchmarking Multi-Step Cartographic Reasoning in Vision-Language Models* — Cartographic reasoning is the skill of interpreting geographic relationships by aligning legends, map scales, compass directions, map texts, and geometries across one or more map images. Although essential as a concrete cognitive capability and for critical tasks such as disaster response and urban planning, it remains largely unevaluated. Building on progress in chart and infographic understanding, recent large vision language model studies on map visual question-answering often treat maps as a special case of charts. In contrast, map VQA demands comprehension of layered symbology (e.g., symbols, geometries, and text labels) as well as spatial relations tied to orientation and distance that

> *From Pixels to Semantics: A Multi-Stage AI Framework for Structural Damage Detection in Satellite Imagery* — Rapid and accurate structural damage assessment following natural disasters is critical for effective emergency response and recovery. However, remote sensing imagery often suffers from low spatial resolution, contextual ambiguity, and limited semantic interpretability, reducing the reliability of traditional detection pipelines. In this work, we propose a novel hybrid framework that integrates AI-based super-resolution, deep learning object detection, and Vision-Language Models (VLMs) for comprehensive post-disaster building damage assessment. First, we enhance pre- and post-disaster satellite imagery using a Video Restoration Transformer (VRT) to upscale images from 1024x1024 to 4096x4096 

Verdict: ☐ OK ☐ ambiguous ☐ wrong

## qa-digital_twin-018

**Q:** What is the total number of buildings in the AuthentiCity knowledge graph?

**A:** 3.6M

> *AuthentiCity: A Multi-Source Provenance-Aware Knowledge Graph and Benchmark for 3D City Models* — Urban digital twins increasingly combine authoritative, crowd-sourced, machine-learned, and reconstructed data with differing reliability, coverage, and semantics. Yet few urban datasets provide a unified representation supporting multi-source integration, provenance tracking, spatial reasoning, and machine learning. We present AuthentiCity, a multi-source, provenance-aware 3D city knowledge graph spanning five cities across three continents (Hamburg, Helsinki, Zurich, New York, and Tokyo) and comprising 180 GiB, 180M nodes, 220M edges, 1.2B properties, and 3.6M buildings. The labeled property graphs integrate authoritative CityGML and OpenStreetMap data for all cities, adding roof-material 

Verdict: ☐ OK ☐ ambiguous ☐ wrong

## qa-digital_twin-020

**Q:** What method is proposed to interpret smart city data and create musical experiences?

**A:** Sonification

> *Musical Smart City: Perspectives on Ubiquitous Sonification* — Smart cities are urban areas with sensor networks that collect data used towards efficient management. As a source of ubiquitous data, smart city initiatives present opportunities to enhance inhabitants' urban awareness. However, making sense of smart city data is challenging and there is a gap between available data and end-user applications. Sonification emerges as a promising method for the interpretation of smart city data and the production of novel musical experiences. In this paper, we first present the smart city paradigm. We then cover the topics of ubiquitous and mobile music, followed by an overview of sonification research. Finally, we propose an approach entitled ubiquitous soni

Verdict: ☐ OK ☐ ambiguous ☐ wrong
