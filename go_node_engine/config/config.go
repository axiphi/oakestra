package config

import (
	"encoding/json"
	"errors"
	"go_node_engine/logger"
	"os"
)

const (
	DefaultLogDir  = "/tmp"
	AutoOakNetwork = "default"

	confDir  = "/etc/oakestra"
	confPath = "/etc/oakestra/conf.json"
)

// RuntimeType is the type of runtime that the node executes
type RuntimeType string

// RuntimeType constants
const (
	CONTAINER_RUNTIME RuntimeType = "docker"
	UNIKERNEL_RUNTIME RuntimeType = "unikernel"
	CROSVM_RUNTIME    RuntimeType = "crosvm"
)

type ConfFile struct {
	ConfVersion     string           `json:"conf_version"`
	ClusterAddress  string           `json:"cluster_address"`
	ClusterSSL      bool             `json:"cluster_ssl"`
	ClusterPort     int              `json:"cluster_port"`
	AppLogs         string           `json:"app_logs"`
	OverlayNetwork  string           `json:"overlay_network"`
	PublicIp        bool             `json:"public_ip"`
	NetPort         int              `json:"overlay_network_port"`
	CertFile        string           `json:"mqtt_cert_file"`
	KeyFile         string           `json:"mqtt_key_file"`
	Addons          []Addon          `json:"addons"`
	Virtualizations []Virtualization `json:"virtualizations"`
	CSIDrivers      []CSIDriverType  `json:"csi_drivers"`
}

type Addon struct {
	Name   string   `json:"addon_name"`
	Active bool     `json:"addon_active"`
	Config []string `json:"addon_config"`
}

type Virtualization struct {
	Name    string   `json:"virtualization_name"`
	Runtime string   `json:"virtualization_runtime"`
	Active  bool     `json:"virtualization_active"`
	Config  []string `json:"virtualization_config"`
}

// CSIDriverType describes a locally available CSI plugin endpoint.
// The Endpoint must point to the plugin's UNIX domain socket, typically
// provided via the CSI_ENDPOINT environment variable or a per-plugin config.
type CSIDriverType struct {
	// Name is the CSI driver name returned by GetPluginInfo (e.g. "nfs.csi.k8s.io")
	Name string `json:"csi_driver_name"`
	// Endpoint is the UNIX domain socket path for this CSI plugin (e.g. "/var/lib/kubelet/plugins/nfs.csi.k8s.io/csi.sock")
	Endpoint string `json:"csi_driver_endpoint"`
}

// Read loads the node configuration from /etc/oakestra/conf.json. If the file
// is missing or empty it writes and returns the default configuration.
func Read() (ConfFile, error) {
	data, err := os.ReadFile(confPath)
	if errors.Is(err, os.ErrNotExist) || (err == nil && len(data) == 0) {
		logger.InfoLogger().Printf("Config file missing or empty, using default configuration")
		def := Default()
		return def, Write(def)
	}
	if err != nil {
		return ConfFile{}, err
	}

	var clusterConf ConfFile
	if err := json.Unmarshal(data, &clusterConf); err != nil {
		logger.ErrorLogger().Printf("Error reading configuration: %v, resetting the file\n", err)
		if resetErr := Write(Default()); resetErr != nil {
			return ConfFile{}, resetErr
		}
		return ConfFile{}, err
	}
	return clusterConf, nil
}

// Write persists the given node configuration to /etc/oakestra/conf.json,
// overwriting any existing content.
func Write(conf ConfFile) error {
	data, err := json.Marshal(conf)
	if err != nil {
		return err
	}
	if err := os.MkdirAll(confDir, 0755); err != nil {
		logger.ErrorLogger().Printf("Failed to create config directory %s: %v\n", confDir, err)
		return err
	}
	return os.WriteFile(confPath, data, 0644)
}

// Default returns the built-in node configuration used when no config file
// exists yet or an existing one cannot be parsed.
func Default() ConfFile {
	return ConfFile{
		ConfVersion:    "1.0",
		ClusterAddress: "0.0.0.0",
		ClusterPort:    10100,
		ClusterSSL:     false,
		AppLogs:        DefaultLogDir,
		OverlayNetwork: AutoOakNetwork,
		PublicIp:       false,
		NetPort:        0,
		Virtualizations: []Virtualization{
			{
				Name:    "containerd",
				Runtime: string(CONTAINER_RUNTIME),
				Active:  true,
				Config:  []string{},
			},
		},
	}
}
