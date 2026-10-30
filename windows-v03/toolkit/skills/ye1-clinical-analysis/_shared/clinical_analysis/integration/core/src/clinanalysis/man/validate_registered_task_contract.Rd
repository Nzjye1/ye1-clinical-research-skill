\name{validate_registered_task_contract}
\alias{validate_registered_task_contract}
\title{Validate an object with a registered task contract}
\usage{
validate_registered_task_contract(object)
}
\arguments{
\item{object}{Task object containing a schema_version.}
}
\value{
Invisibly returns \code{TRUE} or raises a contract error.
}
\description{
Dispatches strict task validation using the object's registered schema version.
}
