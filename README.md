# Data-Drift-reporter
Python + Flask web app to detect data drift between two CSV datasets using statistical analysis. Generates visual reports to monitor ML model input quality.

### video Demo
[watch demo video](https://drive.google.com/file/d/1zOURsDJ_zhvrAtXEka9lSSLAW19d5h5K/view?usp=drivesdk)

### Resume
[view resume](https://drive.google.com/file/d/1AQ-1rxT-aXzyTQ9DXZtV5lv8q1te8Vxk/view?usp=drivesdk)

### case study outputs

## 📊 Case Study & Output Screenshots

### **1. Dataset Comparison View**
Upload baseline & current CSV files. Tool automatically detects columns & data types.
![Dataset Upload](output/drift_datasets.png)

### **2. Drift Analysis Dashboard** 
Statistical comparison with PSI, KS-Test scores. Drifted columns highlighted in red.
![Drift Dashboard](output/drift_dashboard.png)
![Detailed Stats](output/drift_dashboard_2.png)

### **3. Visual Report**
Auto-generated HTML report with charts showing distribution shifts.
![Dataset Summary](output/drift_datasets_2.png)
