\name{register_task_contract}
\alias{register_task_contract}
\title{Register a versioned runtime task contract}
\usage{
register_task_contract(schema_version, validator)
}
\arguments{
\item{schema_version}{Exact task schema version.}
\item{validator}{Function accepting one object and raising a contract error when unsafe.}
}
\description{
Registers a strict task validator under a stable schema version.
}
