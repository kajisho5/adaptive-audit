package cache

// Shared in-memory cache, written from multiple worker goroutines with no lock.
var JobStatus = map[string]string{}

func SetStatus(jobID, status string) {
	JobStatus[jobID] = status // no mutex — concurrent map write hazard
}

func GetStatus(jobID string) string {
	return JobStatus[jobID]
}
